"""Builds a labelled FIELD-level damage dataset from real healthy field photos.

Why this exists: the patch-level coverage/damage models were trained on
collages of random patches with ellipses pasted on (ml/synthetic/
generate_coverage_dataset.py) and measured on 2026-10-22 to read the same
value on a real hopperburn field and a healthy crop. They cannot assess a
field photo. This generator starts from real healthy FIELD photos instead and
paints damage onto them, so the model sees what a field looks like.

For each output image:
  - pick a pest and a target damage % (many low values, ~15% exactly zero);
  - build a mask whose area equals the target, within 0.5 point;
  - recolour only the masked area, keeping the photo's own texture and light;
  - record the damage % MEASURED from the final mask (not the target).

BPH: one to three roughly circular, ragged patches (hopperburn): dried straw
yellow to brown, darker streaks, some surviving green.
RSB: many small clusters and single tillers, pale straw to near white
(dead hearts / white heads), scattered across the photo.

Hard negatives: ~25% of outputs get no damage; a third of those are shifted to
a uniform golden-yellow (ripening look) so the model cannot learn "yellow means
damage". Splits are by BACKGROUND photo, so one photo never appears in two
splits.

Everything produced is SYNTHETIC and labelled as such. It is training data
only; real photos with a technologist's measured damage are the test set
(ml/resnet/evaluate_real_photos.py).

Run from server-python/:
    .venv/bin/python -m ml.synthetic.generate_field_damage_dataset \\
        --backgrounds /path/to/healthy_field_photos --n 1000
"""

import argparse
import csv
import random
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

OUT_ROOT = Path(__file__).resolve().parent / "datasets"
IMAGE_SIZE = (448, 448)
MIN_BG_SIDE = 300
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _smooth_noise(rng: np.random.Generator, shape: tuple[int, int], scale: int) -> np.ndarray:
    small = rng.random((max(2, shape[0] // scale), max(2, shape[1] // scale))).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _blob_mask(rng: np.random.Generator, h: int, w: int, target_frac: float, n_patches: int) -> np.ndarray:
    """Union of ragged ellipses, then thresholded so the area hits the target."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    field = np.zeros((h, w), dtype=np.float32)
    for _ in range(n_patches):
        cy, cx = rng.uniform(0.15, 0.85) * h, rng.uniform(0.15, 0.85) * w
        ry, rx = rng.uniform(0.6, 1.4), rng.uniform(0.6, 1.4)
        dist = np.sqrt(((yy - cy) / (h * ry)) ** 2 + ((xx - cx) / (w * rx)) ** 2)
        field = np.maximum(field, 1.0 - dist)
    field += 0.18 * _smooth_noise(rng, (h, w), 12)  # ragged edge
    return _threshold_to_area(field, target_frac)


def _scatter_mask(rng: np.random.Generator, h: int, w: int, target_frac: float) -> np.ndarray:
    """Many small clusters and single tillers: thresholded sparse noise."""
    field = _smooth_noise(rng, (h, w), 5) + 0.6 * _smooth_noise(rng, (h, w), 14)
    return _threshold_to_area(field, target_frac)


def _threshold_to_area(field: np.ndarray, target_frac: float) -> np.ndarray:
    if target_frac <= 0:
        return np.zeros(field.shape, dtype=bool)
    cutoff = np.quantile(field, 1.0 - target_frac)
    return field > cutoff


def _vertical_noise(rng: np.random.Generator, shape: tuple[int, int]) -> np.ndarray:
    """Noise stretched along the plant axis, so damage follows the leaf direction."""
    h, w = shape
    small = rng.random((max(2, h // 28), max(2, w // 5))).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _damage_colours(rng: np.random.Generator, shape: tuple[int, int], pest: str) -> np.ndarray:
    h, w = shape
    tone = (0.6 * _smooth_noise(rng, (h, w), 16) + 0.4 * _vertical_noise(rng, (h, w)))[..., None]
    if pest == "BPH":
        straw, brown, dark = np.array([178, 150, 88]), np.array([128, 96, 58]), np.array([82, 66, 48])
        base = straw * (1 - tone) + brown * tone
        streak = np.clip((_vertical_noise(rng, (h, w)) - 0.78) / 0.14, 0, 1)[..., None] * 0.55
        return base * (1 - streak) + dark * streak
    pale, white = np.array([214, 196, 148]), np.array([232, 226, 206])
    return pale * (1 - tone) + white * tone


def render(background: Image.Image, pest: str, target_pct: float, rng: np.random.Generator):
    img = background.convert("RGB").resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frac = target_pct / 100.0
    if pest == "BPH":
        mask = _blob_mask(rng, h, w, frac, int(rng.integers(1, 4)))
    else:
        mask = _scatter_mask(rng, h, w, frac)

    if mask.any():
        # Keep the photo's own texture: damage colour scaled by the original luminance.
        lum = arr.mean(axis=2, keepdims=True) / max(arr.mean(), 1.0)
        colour = np.clip(_damage_colours(rng, (h, w), pest) * (0.35 + 0.65 * lum), 0, 255)
        soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.0)), dtype=np.float32)[..., None] / 255.0
        arr = arr * (1 - soft) + colour * soft
    return Image.fromarray(arr.astype(np.uint8)), float(mask.mean() * 100.0), mask


def ripening_shift(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    """Uniform golden-yellow shift: looks like a ripening crop, damage 0."""
    arr = np.asarray(img, dtype=np.float32)
    k = rng.uniform(0.35, 0.6)
    gold = np.array([215, 190, 90], dtype=np.float32)
    lum = arr.mean(axis=2, keepdims=True) / 128.0
    return Image.fromarray(np.clip(arr * (1 - k) + gold * lum * k, 0, 255).astype(np.uint8))


def split_for(name: str) -> str:
    bucket = zlib.crc32(name.encode()) % 100
    return "train" if bucket < 70 else "val" if bucket < 85 else "test"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backgrounds", type=Path, required=True, help="folder of REAL healthy field photos")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=OUT_ROOT / "field_damage_sim")
    args = parser.parse_args()

    paths = sorted(p for p in args.backgrounds.rglob("*") if p.suffix.lower() in EXTENSIONS)
    backgrounds = []
    for p in paths:
        with Image.open(p) as im:
            if min(im.size) >= MIN_BG_SIDE:
                backgrounds.append(p)
    if len(backgrounds) < 10:
        print(f"WARNING: only {len(backgrounds)} usable backgrounds. Splits are by background photo, so a handful "
              "of photos gives a model that has seen almost no real field variety. Use hundreds if you can.")
    if not backgrounds:
        raise SystemExit("no usable background photos found")

    random.seed(args.seed)
    rng = np.random.default_rng(args.seed)
    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "masks").mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.n):
        bg_path = random.choice(backgrounds)
        pest = random.choice(["BPH", "RSB"])
        roll = rng.random()
        with Image.open(bg_path) as bg:
            if roll < 0.25:  # hard negative
                img = bg.convert("RGB").resize(IMAGE_SIZE, Image.LANCZOS)
                mode, pct, mask = "negative-healthy", 0.0, np.zeros(IMAGE_SIZE[::-1], dtype=bool)
                if roll < 0.083:
                    img, mode = ripening_shift(img, rng), "negative-ripening"
            else:
                target = 0.0 if rng.random() < 0.1 else float(np.clip(rng.gamma(2.0, 7.0), 0.5, 40.0))
                img, pct, mask = render(bg, pest, target, rng)
                mode = "field-damage-sim"
        name = f"fd_{i:05d}.jpg"
        img.save(args.out / "images" / name, quality=92)
        Image.fromarray((mask * 255).astype(np.uint8)).save(args.out / "masks" / f"fd_{i:05d}.png")
        rows.append({"filename": name, "pest": pest, "mode": mode, "coverage_pct": round(pct, 3),
                     "background": bg_path.name, "split": split_for(bg_path.name)})

    with (args.out / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "README.md").write_text(
        "SYNTHETIC. Damage painted onto real healthy field photos; training data only. "
        "Label = damage % measured from the saved mask. Split by background photo.\n"
    )
    pcts = np.array([r["coverage_pct"] for r in rows])
    print(f"wrote {len(rows)} images to {args.out}")
    print("damage % quantiles 0/25/50/75/100:", np.round(np.quantile(pcts, [0, .25, .5, .75, 1]), 1))
    for s in ("train", "val", "test"):
        print(s, sum(r["split"] == s for r in rows))


if __name__ == "__main__":
    main()

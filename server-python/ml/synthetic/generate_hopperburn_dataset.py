"""Builds a BPH "hopperburn" field-damage dataset from REAL texture.

Hopperburn is a patch of dried, collapsed rice, straw-yellow to brown. Painted
colour looked fake, so the damage here is filled with REAL dried-rice texture
cut from a real hopperburn photograph (ml/synthetic/textures/), tiled with
random flips and offsets, luminance-matched to the spot it lands on, and
feathered at the edge. The patches are placed on healthy rice-canopy photos
(the Roboflow rice set), larger and flatter near the camera.

Labels: per image coverage_pct (share of pixels inside the damage mask, measured
from the final mask) and, via write_cells, an exact label for each cell of a 3x3
grid, as for the RSB dataset.

About half the negatives are uniform golden "ripening" looks, because a ripening
field is the obvious false alarm for hopperburn. Splits are by background photo.

SYNTHETIC, training data only. The texture comes from ONE photograph, so expect
limited variety: the only honest test is real photos with a measured damage %.

Run from server-python/ (numpy, pillow, scipy):
    python -m ml.synthetic.generate_hopperburn_dataset --backgrounds ~/Downloads/test/rice.v1i.folder --n 1000
"""

import argparse
import csv
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from ml.synthetic.field_backgrounds import find_backgrounds
from ml.synthetic.generate_whitehead_dataset import IMAGE_SIZE, OUT_ROOT, ripening_shift, split_for, write_cells

TEXTURE_DIR = Path(__file__).resolve().parent / "textures"


def load_textures() -> list[np.ndarray]:
    return [np.asarray(Image.open(p).convert("RGB")) for p in sorted(TEXTURE_DIR.glob("hopperburn_real_*.png")) if not p.name.startswith("_")]


def tiled_texture(textures: list[np.ndarray], rng: np.random.Generator, size: int) -> np.ndarray:
    """Fill a size x size canvas with random, flipped crops of the real texture.

    Tiles overlap by half and are blended with a Hann window, so no rectangular
    seams show."""
    tile = 112
    stride = tile // 2
    acc = np.zeros((size + tile, size + tile, 3), dtype=np.float32)
    wsum = np.zeros((size + tile, size + tile, 1), dtype=np.float32)
    win1 = np.hanning(tile).astype(np.float32) + 1e-3
    win = (win1[:, None] * win1[None, :])[..., None]
    for y in range(0, size, stride):
        for x in range(0, size, stride):
            t = textures[rng.integers(len(textures))]
            h, w = t.shape[:2]
            th, tw = min(tile, h), min(tile, w)
            oy, ox = rng.integers(0, h - th + 1), rng.integers(0, w - tw + 1)
            crop = t[oy:oy + th, ox:ox + tw]
            if rng.random() < 0.5:
                crop = crop[:, ::-1]
            if rng.random() < 0.5:
                crop = crop[::-1]
            crop = np.asarray(Image.fromarray(np.ascontiguousarray(crop)).resize((tile, tile), Image.BICUBIC), dtype=np.float32)
            acc[y:y + tile, x:x + tile] += crop * win
            wsum[y:y + tile, x:x + tile] += win
    return (acc / np.maximum(wsum, 1e-6))[:size, :size]


def blob_mask(rng: np.random.Generator, h: int, w: int, target_frac: float) -> np.ndarray:
    """One to three ragged, wide-and-flat patches (perspective makes field patches wider than tall)."""
    if target_frac <= 0:
        return np.zeros((h, w), dtype=bool)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    field = np.zeros((h, w), dtype=np.float32)
    for _ in range(int(rng.integers(1, 4))):
        cy, cx = rng.uniform(0.35, 0.85) * h, rng.uniform(0.15, 0.85) * w
        ry, rx = rng.uniform(0.5, 1.0), rng.uniform(1.0, 2.2)
        field = np.maximum(field, 1.0 - np.sqrt(((yy - cy) / (h * ry)) ** 2 + ((xx - cx) / (w * rx)) ** 2))
    small = rng.random((h // 12 + 2, w // 12 + 2)).astype(np.float32)
    field += 0.2 * np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    cutoff = np.quantile(field, 1.0 - target_frac)
    return field > cutoff


def paint(arr: np.ndarray, mask: np.ndarray, textures: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    h, w = mask.shape
    tex = tiled_texture(textures, rng, max(h, w))[:h, :w]
    # Match the texture's brightness to the photo's own light, so damage is not brighter than the plants around it.
    local = ndimage.uniform_filter(arr.mean(axis=2), size=65)[..., None]
    gain = np.clip((local + 30) / max(tex.mean(), 1.0), 0.75, 1.45)
    tex = np.clip(tex * gain, 0, 255)
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.5)), dtype=np.float32)[..., None] / 255.0
    return (arr * (1 - soft) + tex * soft).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backgrounds", type=Path, required=True)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--max-coverage", type=float, default=45.0)
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "bph_hopperburn_sim")
    ap.add_argument("--cells", type=int, default=3)
    ap.add_argument("--cell-size", type=int, default=160)
    args = ap.parse_args()

    textures = load_textures()
    backgrounds = find_backgrounds(args.backgrounds)
    print(f"{len(textures)} real texture(s), {len(backgrounds)} usable backgrounds")
    if not textures or len(backgrounds) < 30:
        raise SystemExit("need a texture in ml/synthetic/textures and at least 30 backgrounds")

    random.seed(args.seed)
    rng = np.random.default_rng(args.seed)
    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "masks").mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.n):
        roll = rng.random()
        bg_path, _ = random.choice(backgrounds)
        arr = np.asarray(Image.open(bg_path).convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.LANCZOS)).copy()
        mask = np.zeros(arr.shape[:2], dtype=bool)
        mode = "negative-healthy"
        if roll < 0.25:
            if roll < 0.125:
                arr, mode = ripening_shift(arr, rng), "negative-ripening"
        else:
            mode = "hopperburn-texture"
            target = float(np.clip(rng.gamma(1.8, 7.0), 0.5, args.max_coverage)) / 100.0
            mask = blob_mask(rng, *arr.shape[:2], target)
            arr = paint(arr, mask, textures, rng)
        name = f"hb_{i:05d}.jpg"
        Image.fromarray(arr).save(args.out / "images" / name, quality=92)
        Image.fromarray((mask * 255).astype(np.uint8)).save(args.out / "masks" / f"hb_{i:05d}.png")
        rows.append({"filename": name, "pest": "BPH", "mode": mode, "count": int(mask.any()),
                     "coverage_pct": round(float(mask.mean() * 100), 3), "background": bg_path.name, "split": split_for(bg_path.name)})

    with (args.out / "labels.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (args.out / "README.md").write_text(
        "SYNTHETIC. Real hopperburn texture (one photo) painted into masks on real healthy rice-canopy photos. "
        "coverage_pct = share of pixels in the damage mask. Training data only. Split by background photo.\n")
    if args.cells:
        write_cells(args.out, rows, args.cells, args.cell_size)
    pct = np.array([r["coverage_pct"] for r in rows])
    print(f"wrote {len(rows)} images to {args.out}; coverage quantiles 0/25/50/75/100:", np.round(np.quantile(pct, [0, .25, .5, .75, 1]), 1))
    print({s: sum(r["split"] == s for r in rows) for s in ("train", "val", "test")})


if __name__ == "__main__":
    main()

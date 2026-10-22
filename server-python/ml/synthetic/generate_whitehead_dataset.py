"""Builds an RSB "whitehead" field-damage dataset from REAL pieces.

Whiteheads (empty, pale, upright panicles) are the visible RSB damage in the
reproductive stage. The sprites here are not painted: they are cut from real
photos that were edited to show whiteheads, using their masks
(ml/synthetic/datasets/../whitehead_sprites source: a folder of
stemborer_N.png + stemborer_N_mask.png). Each sprite is a real whitehead with
real texture and lighting. They are pasted onto healthy rice-canopy photos in
varying numbers, so one image holds anywhere from none to many.

Placement is perspective-aware: sprites near the bottom of the photo (closer to
the camera) are larger than those near the horizon, are only placed on green
canopy pixels (never sky, mud or water), and are colour- and sharpness-matched
to the spot they land on.

Labels (per image):
  coverage_pct  share of the image's pixels covered by whiteheads, measured from
                the final mask (not the target)
  count         number of whiteheads pasted
The thesis measure for RSB is % of panicles that are whiteheads. Panicles are not
counted in the background photos, so coverage_pct is a PROXY for it and must be
labelled as such. A technologist's measured % on real photos is the real test.

~25% of images are hard negatives with no whiteheads; a third of those get a
uniform golden "ripening" shift so yellow does not mean damage. Splits are by
background photo.

Everything produced is SYNTHETIC and is training data only.

Run from server-python/ (needs numpy, pillow, scipy):
    python -m ml.synthetic.generate_whitehead_dataset \\
        --backgrounds ~/Downloads/test/rice.v1i.folder \\
        --sprites ~/Downloads/test/ysb_damaged --n 300
"""

import argparse
import csv
import random
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from ml.synthetic.field_backgrounds import find_backgrounds

OUT_ROOT = Path(__file__).resolve().parent / "datasets"
IMAGE_SIZE = 448
MIN_SPRITE_PX = 60
MAX_SPRITE_PX = 6000


def load_sprites(folder: Path) -> list[dict]:
    """Cut every whitehead out of every stemborer_N / stemborer_N_mask pair."""
    sprites = []
    for img_path in sorted(folder.glob("stemborer_*.png")):
        if img_path.stem.endswith("_mask") or "(" in img_path.stem:
            continue
        mask_path = img_path.with_name(img_path.stem + "_mask.png")
        if not mask_path.exists():
            continue
        img = Image.open(img_path).convert("RGB")
        mask = np.asarray(Image.open(mask_path).convert("L").resize(img.size)) > 127
        arr = np.asarray(img)
        labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
        scale = 1.0 / min(img.size)  # size relative to the source photo, so sources of any resolution agree
        for sl, idx in zip(ndimage.find_objects(labels), range(1, n + 1)):
            comp = labels[sl] == idx
            area = int(comp.sum())
            if not MIN_SPRITE_PX <= area <= MAX_SPRITE_PX:
                continue
            pad = 3
            y0, y1 = max(sl[0].start - pad, 0), min(sl[0].stop + pad, mask.shape[0])
            x0, x1 = max(sl[1].start - pad, 0), min(sl[1].stop + pad, mask.shape[1])
            alpha = ndimage.binary_dilation(labels[y0:y1, x0:x1] == idx, iterations=1)
            sprites.append({
                "rgb": arr[y0:y1, x0:x1].copy(),
                "alpha": alpha.astype(np.float32),
                "rel_height": (y1 - y0) * scale,  # fraction of the source photo's short side
            })
    return sprites


def canopy_mask(arr: np.ndarray) -> np.ndarray:
    r, g, b = (arr[..., i].astype(np.float32) for i in range(3))
    return ((2 * g - r - b) > 20) & (g > 55)


def paste_one(canvas: np.ndarray, mask: np.ndarray, canopy: np.ndarray, sprite: dict, rng: np.random.Generator,
              blur_sigma: float) -> bool:
    h, w = canvas.shape[:2]
    ys, xs = np.nonzero(canopy)
    if len(ys) < 500:
        return False
    # Bias towards the lower part of the photo, where plants are closer and larger.
    weights = (ys / h) ** 1.5 + 0.05
    k = rng.choice(len(ys), p=weights / weights.sum())
    cy, cx = int(ys[k]), int(xs[k])
    depth = 0.45 + 1.0 * (cy / h)  # far = small, near = large
    target_h = max(8, sprite["rel_height"] * min(h, w) * depth * rng.uniform(0.8, 1.25) * 0.9)
    f = target_h / sprite["rgb"].shape[0]
    rgb = Image.fromarray(sprite["rgb"]).resize((max(3, int(sprite["rgb"].shape[1] * f)), max(3, int(target_h))), Image.LANCZOS)
    alpha = Image.fromarray((sprite["alpha"] * 255).astype(np.uint8)).resize(rgb.size, Image.BILINEAR)
    if rng.random() < 0.5:
        rgb, alpha = rgb.transpose(Image.FLIP_LEFT_RIGHT), alpha.transpose(Image.FLIP_LEFT_RIGHT)
    ang = rng.uniform(-14, 14)
    rgb, alpha = rgb.rotate(ang, expand=True, resample=Image.BICUBIC), alpha.rotate(ang, expand=True, resample=Image.BICUBIC)
    if blur_sigma > 0.3:
        rgb, alpha = rgb.filter(ImageFilter.GaussianBlur(blur_sigma)), alpha.filter(ImageFilter.GaussianBlur(blur_sigma * 0.6))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    sw, sh = rgb.size
    x0, y1 = cx - sw // 2, cy  # sprite's base sits on the canopy pixel
    y0 = y1 - sh
    px0, py0, px1, py1 = max(x0, 0), max(y0, 0), min(x0 + sw, w), min(y1, h)
    if px1 - px0 < 3 or py1 - py0 < 3:
        return False
    s_rgb = np.asarray(rgb, dtype=np.float32)[py0 - y0:py1 - y0, px0 - x0:px1 - x0]
    s_a = np.asarray(alpha, dtype=np.float32)[py0 - y0:py1 - y0, px0 - x0:px1 - x0] / 255.0
    region = canvas[py0:py1, px0:px1].astype(np.float32)
    # Match brightness to the spot it lands on (partially: whiteheads stay paler than the canopy).
    gain = np.clip((region.mean() + 55) / max(s_rgb[s_a > 0.5].mean() if (s_a > 0.5).any() else 1.0, 1.0), 0.85, 1.45)
    s_rgb = np.clip(s_rgb * gain, 0, 255)
    canvas[py0:py1, px0:px1] = (region * (1 - s_a[..., None]) + s_rgb * s_a[..., None]).astype(np.uint8)
    mask[py0:py1, px0:px1] |= s_a > 0.5
    return True


def ripening_shift(arr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    k = rng.uniform(0.3, 0.55)
    gold = np.array([215, 190, 90], dtype=np.float32)
    lum = arr.astype(np.float32).mean(axis=2, keepdims=True) / 128.0
    return np.clip(arr * (1 - k) + gold * lum * k, 0, 255).astype(np.uint8)


def write_cells(out: Path, rows: list[dict], grid: int, cell_size: int) -> None:
    """Cut every image into grid x grid cells with an exact label from the mask.

    A cell label is the share of the cell's pixels covered by whiteheads. Each
    cell is enlarged to cell_size, so thin whiteheads keep their detail instead
    of being lost when a whole photo is shrunk. Cells inherit the image's split.
    The mean of an image's cell labels equals its whole-image coverage, and the
    share of cells with any whitehead is the spread across the photo.
    """
    (out / "cells").mkdir(exist_ok=True)
    cell_rows = []
    for r in rows:
        img = Image.open(out / "images" / r["filename"]).convert("RGB")
        mask = np.asarray(Image.open(out / "masks" / r["filename"].replace(".jpg", ".png")).convert("L")) > 127
        h, w = mask.shape
        for gy in range(grid):
            for gx in range(grid):
                box = (gx * w // grid, gy * h // grid, (gx + 1) * w // grid, (gy + 1) * h // grid)
                name = f"{r['filename'][:-4]}_c{gy}{gx}.jpg"
                img.crop(box).resize((cell_size, cell_size), Image.LANCZOS).save(out / "cells" / name, quality=92)
                cell_rows.append({"filename": name, "image": r["filename"], "row": gy, "col": gx,
                                  "coverage_pct": round(float(mask[box[1]:box[3], box[0]:box[2]].mean() * 100), 3),
                                  "split": r["split"]})
    with (out / "cell_labels.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(cell_rows[0]))
        wr.writeheader()
        wr.writerows(cell_rows)
    print(f"wrote {len(cell_rows)} cells ({grid}x{grid} per image, {cell_size}px) to {out / 'cells'}")


def split_for(name: str) -> str:
    b = zlib.crc32(name.encode()) % 100
    return "train" if b < 70 else "val" if b < 85 else "test"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backgrounds", type=Path, required=True)
    ap.add_argument("--sprites", type=Path, required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-coverage", type=float, default=8.0, help="upper bound of target coverage, percent of pixels")
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "rsb_whitehead_sim")
    ap.add_argument("--cells", type=int, default=3, help="also write an N x N grid of labelled cells per image (0 = off)")
    ap.add_argument("--cell-size", type=int, default=160)
    args = ap.parse_args()

    sprites = load_sprites(args.sprites)
    backgrounds = find_backgrounds(args.backgrounds)
    print(f"{len(sprites)} real whitehead sprites, {len(backgrounds)} usable backgrounds")
    if len(sprites) < 20 or len(backgrounds) < 30:
        raise SystemExit("need at least 20 sprites and 30 backgrounds")

    # Damage goes on reproductive-stage photos (the stage whiteheads occur in); the others serve as negatives.
    repro = [(p, s) for p, s in backgrounds if any(k in p.name for k in ("flowering", "full_growth", "undefined"))]
    random.seed(args.seed)
    rng = np.random.default_rng(args.seed)
    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "masks").mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.n):
        roll = rng.random()
        negative = roll < 0.25
        bg_path, st = random.choice(backgrounds if negative else repro)
        arr = np.asarray(Image.open(bg_path).convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.LANCZOS)).copy()
        mask = np.zeros(arr.shape[:2], dtype=bool)
        count = 0
        mode = "negative-healthy"
        if negative:
            if roll < 0.083:
                arr, mode = ripening_shift(arr, rng), "negative-ripening"
        else:
            mode = "whitehead-paste"
            target = 0.0 if rng.random() < 0.06 else float(np.clip(rng.gamma(1.6, 1.5), 0.2, args.max_coverage))
            canopy = canopy_mask(arr)
            blur = float(np.clip(2.2 - st["sharp"] / 60.0, 0, 1.6))  # soften sprites on soft photos
            attempts = 0
            while mask.mean() * 100 < target and attempts < 400:
                attempts += 1
                count += paste_one(arr, mask, canopy, random.choice(sprites), rng, blur)
        name = f"wh_{i:05d}.jpg"
        Image.fromarray(arr).save(args.out / "images" / name, quality=92)
        Image.fromarray((mask * 255).astype(np.uint8)).save(args.out / "masks" / f"wh_{i:05d}.png")
        rows.append({"filename": name, "pest": "RSB", "mode": mode, "count": count,
                     "coverage_pct": round(float(mask.mean() * 100), 3), "background": bg_path.name, "split": split_for(bg_path.name)})

    with (args.out / "labels.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (args.out / "README.md").write_text(
        "SYNTHETIC. Real whitehead sprites (cut from edited field photos with their masks) pasted onto real healthy "
        "rice-canopy photos. coverage_pct = pixel share covered by whiteheads (a proxy for % white ears). Training data only. "
        "Backgrounds: Roboflow rice-kkqe5 (CC BY 4.0). Split by background photo.\n"
    )
    if args.cells:
        write_cells(args.out, rows, args.cells, args.cell_size)
    pct = np.array([r["coverage_pct"] for r in rows])
    print(f"wrote {len(rows)} images to {args.out}")
    print("coverage % quantiles 0/25/50/75/100:", np.round(np.quantile(pct, [0, .25, .5, .75, 1]), 2))
    print({s: sum(r["split"] == s for r in rows) for s in ("train", "val", "test")},
          "negatives:", sum(r["mode"].startswith("negative") for r in rows))


if __name__ == "__main__":
    main()

"""Shared crop-extraction helper for the ResNet-50 pest classifiers.

Each pest's raw data is a Roboflow-exported folder: a flat directory of
416x416 images plus a `_annotations.csv` (Pascal VOC style: filename, width,
height, class, xmin, ymin, xmax, ymax; one row per box, images with
multiple pests in frame have multiple rows). This module turns those boxes
into individual cropped images on disk, one file per box, which is what the
classifier actually trains on (crop-then-classify, not detection) — see
ml/resnet/prepare_bph.py and prepare_rsb.py for how each pest's positive and
negative folders are combined.
"""

import random
from pathlib import Path

import pandas as pd
from PIL import Image

MIN_BOX_SIDE_PX = 10  # drops degenerate/near-zero-area annotation noise
PADDING_FRAC = 0.15  # extra margin around each box, as a fraction of its own size

MIN_BACKGROUND_SIDE_PX = 16
BACKGROUND_MAX_ATTEMPTS = 40  # per patch, before giving up on a crowded image


def load_annotations(folder: Path) -> pd.DataFrame:
    df = pd.read_csv(folder / "_annotations.csv")
    width = df["xmax"] - df["xmin"]
    height = df["ymax"] - df["ymin"]
    return df[(width >= MIN_BOX_SIDE_PX) & (height >= MIN_BOX_SIDE_PX)].reset_index(drop=True)


def extract_crops(folder: Path, out_dir: Path, prefix: str) -> int:
    """Crops every valid box in `folder`'s _annotations.csv out of its
    source image (with a small padding margin, clamped to image bounds) and
    saves each as its own file under `out_dir`. Returns how many crops were
    written. `prefix` disambiguates crops across source folders that would
    otherwise produce clashing filenames (e.g. both bph/ and sb/ contain a
    row numbered 0 for their first image)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    annotations = load_annotations(folder)

    written = 0
    for filename, group in annotations.groupby("filename"):
        image_path = folder / filename
        if not image_path.exists():
            continue
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img_w, img_h = img.size

            for i, row in enumerate(group.itertuples(index=False)):
                box_w = row.xmax - row.xmin
                box_h = row.ymax - row.ymin
                pad_x = int(box_w * PADDING_FRAC)
                pad_y = int(box_h * PADDING_FRAC)

                left = max(0, row.xmin - pad_x)
                top = max(0, row.ymin - pad_y)
                right = min(img_w, row.xmax + pad_x)
                bottom = min(img_h, row.ymax + pad_y)

                crop = img.crop((left, top, right, bottom))
                crop.save(out_dir / f"{prefix}_{Path(filename).stem}_{i}.jpg", quality=95)
                written += 1

    return written


def padded_box_sides(folder: Path) -> list[int]:
    """Side length (in source-image pixels) of every valid crop
    extract_crops() would produce from `folder` — used to size background
    patches the same way, so "empty" examples are the same scale as the
    insect crops the model sees."""
    df = load_annotations(folder)
    sides = ((df["xmax"] - df["xmin"]) + (df["ymax"] - df["ymin"])) / 2 * (1 + 2 * PADDING_FRAC)
    return [int(s) for s in sides]


def extract_background(
    folder: Path, out_dir: Path, prefix: str, patches_per_image: float, target_sides: list[int], seed: int = 42
) -> int:
    """Cuts square patches from `folder`'s images out of areas that overlap
    NO annotated box (every box in the csv, padded like a crop — including
    ones too small for extract_crops to keep), so leaf, water, soil and
    stalks become real negative examples. Without these the classifier has
    only ever seen "this pest" vs "other insects" and fires on empty
    background when a photo is cut into a grid.

    Patch side lengths are drawn from `target_sides` (see padded_box_sides).
    `patches_per_image` may be fractional (0.4 = a patch from ~40% of
    images). Files are named `{prefix}_{source-stem}_bg{k}.jpg` so
    ml/resnet/prepare_dataset.py:split_bucket() puts each patch in the same
    train/val/test split as the crops from that same source image.
    Deterministic for a given seed. Returns how many patches were written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(folder / "_annotations.csv")
    boxes_by_file: dict[str, list[tuple[int, int, int, int]]] = {}
    for row in raw.itertuples(index=False):
        pad_x = int((row.xmax - row.xmin) * PADDING_FRAC)
        pad_y = int((row.ymax - row.ymin) * PADDING_FRAC)
        boxes_by_file.setdefault(row.filename, []).append(
            (row.xmin - pad_x, row.ymin - pad_y, row.xmax + pad_x, row.ymax + pad_y)
        )

    written = 0
    for image_path in sorted(folder.glob("*.jpg")):
        rng = random.Random(f"{seed}-{image_path.name}")
        wanted = int(patches_per_image) + (1 if rng.random() < patches_per_image - int(patches_per_image) else 0)
        if wanted == 0:
            continue

        boxes = boxes_by_file.get(image_path.name, [])
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img_w, img_h = img.size

            saved_here = 0
            for _ in range(wanted):
                for _attempt in range(BACKGROUND_MAX_ATTEMPTS):
                    side = max(MIN_BACKGROUND_SIDE_PX, min(rng.choice(target_sides), img_w, img_h))
                    x = rng.randint(0, img_w - side)
                    y = rng.randint(0, img_h - side)
                    overlaps = any(
                        not (x + side <= bx0 or x >= bx1 or y + side <= by0 or y >= by1)
                        for bx0, by0, bx1, by1 in boxes
                    )
                    if overlaps:
                        continue
                    img.crop((x, y, x + side, y + side)).save(
                        out_dir / f"{prefix}_{image_path.stem}_bg{saved_here}.jpg", quality=95
                    )
                    saved_here += 1
                    written += 1
                    break

    return written

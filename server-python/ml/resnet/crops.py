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

from pathlib import Path

import pandas as pd
from PIL import Image

MIN_BOX_SIDE_PX = 10  # drops degenerate/near-zero-area annotation noise
PADDING_FRAC = 0.15  # extra margin around each box, as a fraction of its own size


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

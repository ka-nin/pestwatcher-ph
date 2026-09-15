"""Builds the crop-then-classify training set for one pest's ResNet-50
binary classifier (BPH or RSB).

Each pest's classifier answers "is this pest in this crop, yes or no" — so
positives are that pest's own annotated boxes, and negatives are every other
annotated pest's boxes: the other target pest (ml/resnet/bph or
ml/resnet/sb) plus the four other rice pests in ml/resnet/negative
(whorl-maggot, leaf-folder, rice-bug, green-leafhopper). Without real
negatives from other insects, the model would only learn to distinguish
"BPH vs RSB" rather than "BPH vs not-BPH", and would be forced into a
confident wrong answer on any other insect a farmer photographs.

Crops are extracted via ml/resnet/crops.py, then split 70/15/15 by a
filename-based hash (not sklearn's random split) so every crop from the same
source image lands in the same split — otherwise near-duplicate crops from
one heavily-annotated image (some images have 40+ boxes) could leak across
train/test and inflate reported accuracy.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest BPH
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest RSB
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from ml.resnet.crops import extract_crops

RESNET_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = RESNET_DIR / "datasets" / "processed"

PEST_SOURCE_DIRS = {
    "BPH": RESNET_DIR / "bph",
    "RSB": RESNET_DIR / "sb",
}
NEGATIVE_DIR = RESNET_DIR / "negative"

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
# TEST_FRACTION is whatever remains (~0.15)


def split_bucket(filename: str) -> str:
    """Deterministic hash-based split keyed on the ORIGINAL source image
    filename (before the crop index suffix), so every crop from the same
    image always lands in the same bucket."""
    stem = filename.rsplit("_", 1)[0]  # strip the "_<crop-index>" suffix added by extract_crops
    digest = int(hashlib.sha1(stem.encode()).hexdigest(), 16)
    fraction = (digest % 10_000) / 10_000
    if fraction < TRAIN_FRACTION:
        return "train"
    if fraction < TRAIN_FRACTION + VAL_FRACTION:
        return "val"
    return "test"


def distribute_crops(source_dir: Path, label: str, pest_out_dir: Path) -> dict[str, int]:
    counts = {"train": 0, "val": 0, "test": 0}
    for crop_path in source_dir.glob("*.jpg"):
        bucket = split_bucket(crop_path.name)
        dest_dir = pest_out_dir / bucket / label
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(crop_path, dest_dir / crop_path.name)
        counts[bucket] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = parser.parse_args()
    pest = args.pest

    positive_source = PEST_SOURCE_DIRS[pest]
    negative_pest_source = PEST_SOURCE_DIRS["RSB" if pest == "BPH" else "BPH"]

    pest_out_dir = PROCESSED_DIR / pest.lower()
    crops_tmp_dir = pest_out_dir / "_crops_tmp"
    if crops_tmp_dir.exists():
        shutil.rmtree(crops_tmp_dir)
    for split in ("train", "val", "test"):
        split_dir = pest_out_dir / split
        if split_dir.exists():
            shutil.rmtree(split_dir)

    positive_crops_dir = crops_tmp_dir / "positive"
    other_pest_crops_dir = crops_tmp_dir / "other_pest"
    negative_crops_dir = crops_tmp_dir / "negative"

    n_positive = extract_crops(positive_source, positive_crops_dir, prefix="pos")
    n_other_pest = extract_crops(negative_pest_source, other_pest_crops_dir, prefix="otherpest")
    n_negative = extract_crops(NEGATIVE_DIR, negative_crops_dir, prefix="neg")

    print(f"{pest}: extracted {n_positive} positive crops, {n_other_pest} other-pest crops, {n_negative} negative crops")

    summary: dict[str, dict[str, int]] = {"positive": {"train": 0, "val": 0, "test": 0}, "negative": {"train": 0, "val": 0, "test": 0}}

    pos_counts = distribute_crops(positive_crops_dir, "positive", pest_out_dir)
    for split, n in pos_counts.items():
        summary["positive"][split] += n

    for source_dir in (other_pest_crops_dir, negative_crops_dir):
        neg_counts = distribute_crops(source_dir, "negative", pest_out_dir)
        for split, n in neg_counts.items():
            summary["negative"][split] += n

    shutil.rmtree(crops_tmp_dir)

    summary_path = pest_out_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"{pest} split summary: {json.dumps(summary, indent=2)}")
    print(f"Saved crops to {pest_out_dir}/{{train,val,test}}/{{positive,negative}}/")


if __name__ == "__main__":
    main()

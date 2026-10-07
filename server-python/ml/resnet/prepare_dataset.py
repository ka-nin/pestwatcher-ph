"""Builds the crop-then-classify training set for one pest's ResNet-50
binary classifier (BPH or RSB).

Each pest's classifier answers "is this pest in this crop, yes or no" — so
positives are that pest's own annotated boxes, and negatives are every other
annotated pest's boxes: the other target pest (ml/resnet/bph or
ml/resnet/sb, plus ml/resnet/datasets/rsb_larva/ for RSB — see below) plus
the four other rice pests in ml/resnet/negative (whorl-maggot, leaf-folder,
rice-bug, green-leafhopper). Without real negatives from other insects, the
model would only learn to distinguish "BPH vs RSB" rather than "BPH vs
not-BPH", and would be forced into a confident wrong answer on any other
insect a farmer photographs.

RSB's positive class is sourced from TWO folders, not one:
ml/resnet/sb/ (the original Roboflow export — almost entirely adult-moth
photographs; its one class, "stem-borer", doesn't distinguish life stage)
and ml/resnet/datasets/rsb_larva/ (added later — real larva crops, class
"Stem-Borer-Larvae"). A classifier trained on sb/ alone only learns "is
there an adult moth here", which is a narrower thing than what the thesis's
ETL table actually cares about (dead hearts/white ears are larval damage).
BPH stays single-source. See PEST_SOURCE_DIRS.

Crops are extracted via ml/resnet/crops.py, then split 70/15/15 by a
filename-based hash (not sklearn's random split) so every crop from the same
source image lands in the same split — otherwise near-duplicate crops from
one heavily-annotated image (some images have 40+ boxes) could leak across
train/test and inflate reported accuracy.

Background patches (on by default) are added as extra negatives: squares cut
from the same images but from areas that overlap no annotated box, sized like
this pest's own insect crops (see crops.extract_background). Every crop above
is an insect, so without them the model has never seen empty leaf, water or
soil and fires on it when a photo is cut into a grid (app/preprocessing/
tiling.py). Pass --no-background to rebuild the original crop-only dataset.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest BPH
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest RSB
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from ml.resnet.crops import extract_background, extract_crops, padded_box_sides

RESNET_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = RESNET_DIR / "datasets" / "processed"

LARVA_DIR = RESNET_DIR / "datasets" / "rsb_larva"

# Each pest's positive source is a LIST of folders now, not one — RSB's
# original `sb/` export is almost entirely adult-moth photographs (its
# single Roboflow class, "stem-borer", doesn't distinguish life stage), so
# a classifier trained on it alone only learns "is there an adult moth
# here", not "is there a stem borer" in the broader sense the thesis's ETL
# table implies (dead hearts/white ears are larval damage, not moth
# sightings). `rsb_larva/` adds real larva crops (class "Stem-Borer-Larvae",
# sourced via ml/resnet/README or the conversation that added it) as a
# second positive source for the same binary label. Every place below that
# used to take one Path now loops over a list and merges the results.
PEST_SOURCE_DIRS: dict[str, list[Path]] = {
    "BPH": [RESNET_DIR / "bph"],
    "RSB": [RESNET_DIR / "sb", LARVA_DIR],
}
NEGATIVE_DIR = RESNET_DIR / "negative"

# Background patches per source image, by which folder the image came from:
# the target pest's own photos are the scenes the model will actually see, so
# they get the most; the big negative folder already contributes thousands of
# insect crops, so it gets a light touch. Together ~3,000 patches for BPH,
# roughly a third of the existing negatives.
BACKGROUND_PER_IMAGE = {"positive": 2.0, "other_pest": 1.0, "negative": 0.4}

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
    parser.add_argument("--no-background", action="store_true", help="skip background patches (original crop-only dataset)")
    args = parser.parse_args()
    pest = args.pest

    positive_sources = PEST_SOURCE_DIRS[pest]
    negative_pest_sources = PEST_SOURCE_DIRS["RSB" if pest == "BPH" else "BPH"]

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

    # `prefix` disambiguates crops across source folders that would otherwise
    # clash on filename (crops.extract_crops's own docstring) — each source
    # folder gets its own prefix (source directory name) rather than reusing
    # "pos"/"otherpest" for every folder in the list.
    n_positive = sum(
        extract_crops(source, positive_crops_dir, prefix=f"pos-{source.name}") for source in positive_sources
    )
    n_other_pest = sum(
        extract_crops(source, other_pest_crops_dir, prefix=f"otherpest-{source.name}")
        for source in negative_pest_sources
    )
    n_negative = extract_crops(NEGATIVE_DIR, negative_crops_dir, prefix="neg")

    print(f"{pest}: extracted {n_positive} positive crops, {n_other_pest} other-pest crops, {n_negative} negative crops")

    summary: dict[str, dict[str, int]] = {"positive": {"train": 0, "val": 0, "test": 0}, "negative": {"train": 0, "val": 0, "test": 0}}

    background_dirs: list[Path] = []
    if not args.no_background:
        background_sources: list[tuple[str, Path, str]] = [
            ("positive", source, f"pos-{source.name}") for source in positive_sources
        ] + [
            ("other_pest", source, f"otherpest-{source.name}") for source in negative_pest_sources
        ] + [
            ("negative", NEGATIVE_DIR, "neg"),
        ]
        for role, source, prefix in background_sources:
            # Each source's own box sizes, not the first source's — a larva
            # crop is much smaller than a moth crop, so sizing every
            # background patch off one source would mismatch the other.
            target_sides = padded_box_sides(source)
            out_dir = crops_tmp_dir / f"background_{role}_{source.name}"
            n = extract_background(source, out_dir, prefix, BACKGROUND_PER_IMAGE[role], target_sides)
            print(f"{pest}: extracted {n} background patches from {source.name}/")
            background_dirs.append(out_dir)
        summary["background_in_negative"] = {"train": 0, "val": 0, "test": 0}

    pos_counts = distribute_crops(positive_crops_dir, "positive", pest_out_dir)
    for split, n in pos_counts.items():
        summary["positive"][split] += n

    for source_dir in (other_pest_crops_dir, negative_crops_dir, *background_dirs):
        neg_counts = distribute_crops(source_dir, "negative", pest_out_dir)
        for split, n in neg_counts.items():
            summary["negative"][split] += n
            if source_dir in background_dirs:
                summary["background_in_negative"][split] += n

    shutil.rmtree(crops_tmp_dir)

    summary_path = pest_out_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"{pest} split summary: {json.dumps(summary, indent=2)}")
    print(f"Saved crops to {pest_out_dir}/{{train,val,test}}/{{positive,negative}}/")


if __name__ == "__main__":
    main()

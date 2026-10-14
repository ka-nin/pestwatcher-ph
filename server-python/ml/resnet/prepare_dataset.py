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

Whole, realistically-framed negatives from unknown_negatives/ (see
UNKNOWN_WHOLE_IMAGE_NEGATIVE_DIRS below) are also mixed in, for the same
reason they were added to the UNKNOWN classifier: a tight insect-sized crop
or background patch is not the same distribution as a normal photo a farmer
actually uploads, so without them BPH/RSB had no real exposure to "a whole
photo with no pest in it" and could swing to high-confidence false positives
on things as unrelated as a beaver (see the conversation that added this).

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest BPH
    .venv/Scripts/python.exe -m ml.resnet.prepare_dataset --pest RSB
"""

import argparse
import csv
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

# "UNKNOWN" is a third, separate binary classifier: not "which pest" but "is
# there any insect in frame at all" (bug vs. no-bug), so a photo of an
# unrelated insect (e.g. a butterfly) reads as "unidentified pest detected"
# instead of being lumped in with truly empty photos as "no pest detected".
# Positives are every insect crop already collected for the other two models
# (BPH, RSB's two sources, the four unrelated pests in negative/) plus a
# general insect-classification export (unidentified/) that has no bounding
# boxes — those whole images are used directly instead of being cropped.
# Negatives are background patches (empty leaf/water/soil, cropped the same
# tight way as an insect box) PLUS whole, realistically-framed photos from
# unknown_negatives/ — the patches alone turned out not to be enough: they
# only ever taught the model "zoomed-in texture with no insect", so a real,
# normally-framed photo (an empty field, or anything unrelated like a random
# object) was out-of-distribution and often scored as "insect present"
# anyway. unknown_negatives/healthy_rice (real rice-leaf photos confirmed
# pest-free by their own Roboflow label) and /not_rice_leaf (that same
# dataset's "not a rice leaf" class) fix the "empty field" blind spot;
# /caltech101 (a sample of the public Caltech-101 object dataset) fixes the
# "totally unrelated photo" blind spot. See ml/resnet/README or the
# conversation that added this for how each was sourced.
UNKNOWN_BOX_SOURCE_DIRS: list[Path] = [RESNET_DIR / "bph", RESNET_DIR / "sb", LARVA_DIR, NEGATIVE_DIR]
UNIDENTIFIED_DIR = RESNET_DIR / "unidentified"
UNIDENTIFIED_SPLITS = ("train", "valid", "test")  # Roboflow's own split folders, merged and re-split below

UNKNOWN_WHOLE_IMAGE_NEGATIVE_DIRS: list[Path] = [
    RESNET_DIR / "unknown_negatives" / "healthy_rice",
    RESNET_DIR / "unknown_negatives" / "not_rice_leaf",
    RESNET_DIR / "unknown_negatives" / "caltech101",
]

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


def extract_unidentified_images(out_dir: Path) -> int:
    """Copies every image from unidentified/{train,valid,test}/_classes.csv
    whose row has at least one class column set to 1 — i.e. some insect is
    present, regardless of which species — into `out_dir`, prefixed so
    filenames can't clash with the other positive sources. Unlike
    extract_crops, these are whole images (no bounding boxes in this
    Roboflow export), which is fine here since the "UNKNOWN" model only
    needs to learn "insect somewhere in frame", not a tight crop around it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for split in UNIDENTIFIED_SPLITS:
        split_dir = UNIDENTIFIED_DIR / split
        classes_csv = split_dir / "_classes.csv"
        if not classes_csv.exists():
            continue
        with open(classes_csv, newline="") as f:
            reader = csv.DictReader(f, skipinitialspace=True)
            for row in reader:
                filename = row["filename"].strip()
                has_insect = any(
                    v.strip() == "1" for k, v in row.items() if k and k.strip() != "filename"
                )
                if not has_insect:
                    continue
                src = split_dir / filename
                if not src.exists():
                    continue
                shutil.copy2(src, out_dir / f"unidentified-{split}_{filename}")
                written += 1
    return written


def extract_whole_images(source_dir: Path, out_dir: Path, prefix: str) -> int:
    """Copies every image straight from a flat folder with no annotations —
    used for unknown_negatives/* (healthy_rice, not_rice_leaf, caltech101),
    which are plain, realistically-framed photos rather than Roboflow
    exports with bounding boxes or a _classes.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for img_path in sorted(source_dir.glob("*.jpg")):
        shutil.copy2(img_path, out_dir / f"{prefix}_{img_path.name}")
        written += 1
    return written


def prepare_unknown(args: argparse.Namespace) -> None:
    """UNKNOWN: "is any insect in frame" (bug vs. no-bug), not which pest.
    Positives: every insect crop from BPH/RSB/negative/, plus whole images
    from unidentified/. Negatives: background patches (empty leaf/water/soil
    crops, same scale as an insect box) PLUS whole realistic photos from
    unknown_negatives/ (empty rice-leaf photos and unrelated Caltech-101
    objects) — the patches alone left the model untrained on normally-framed
    photos entirely, see UNKNOWN_WHOLE_IMAGE_NEGATIVE_DIRS's comment."""
    pest_out_dir = PROCESSED_DIR / "unknown"
    crops_tmp_dir = pest_out_dir / "_crops_tmp"
    if crops_tmp_dir.exists():
        shutil.rmtree(crops_tmp_dir)
    for split in ("train", "val", "test"):
        split_dir = pest_out_dir / split
        if split_dir.exists():
            shutil.rmtree(split_dir)

    positive_crops_dir = crops_tmp_dir / "positive"
    n_boxed = sum(
        extract_crops(source, positive_crops_dir, prefix=f"pos-{source.name}")
        for source in UNKNOWN_BOX_SOURCE_DIRS
    )
    n_unidentified = extract_unidentified_images(positive_crops_dir)
    print(f"UNKNOWN: extracted {n_boxed} boxed insect crops, {n_unidentified} unidentified-insect images")

    summary: dict[str, dict[str, int]] = {"positive": {"train": 0, "val": 0, "test": 0}, "negative": {"train": 0, "val": 0, "test": 0}}

    background_dirs: list[Path] = []
    if not args.no_background:
        for source in UNKNOWN_BOX_SOURCE_DIRS:
            target_sides = padded_box_sides(source)
            out_dir = crops_tmp_dir / f"background_{source.name}"
            n = extract_background(source, out_dir, source.name, BACKGROUND_PER_IMAGE["negative"], target_sides)
            print(f"UNKNOWN: extracted {n} background patches from {source.name}/")
            background_dirs.append(out_dir)

    whole_image_negative_dir = crops_tmp_dir / "whole_image_negatives"
    n_whole_negatives = sum(
        extract_whole_images(source, whole_image_negative_dir, prefix=source.name)
        for source in UNKNOWN_WHOLE_IMAGE_NEGATIVE_DIRS
        if source.exists()
    )
    print(f"UNKNOWN: extracted {n_whole_negatives} whole-image negatives from unknown_negatives/")

    pos_counts = distribute_crops(positive_crops_dir, "positive", pest_out_dir)
    for split, n in pos_counts.items():
        summary["positive"][split] += n

    for source_dir in (*background_dirs, whole_image_negative_dir):
        neg_counts = distribute_crops(source_dir, "negative", pest_out_dir)
        for split, n in neg_counts.items():
            summary["negative"][split] += n

    shutil.rmtree(crops_tmp_dir)

    summary_path = pest_out_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"UNKNOWN split summary: {json.dumps(summary, indent=2)}")
    print(f"Saved crops to {pest_out_dir}/{{train,val,test}}/{{positive,negative}}/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB", "UNKNOWN"], required=True)
    parser.add_argument("--no-background", action="store_true", help="skip background patches (original crop-only dataset)")
    args = parser.parse_args()
    pest = args.pest

    if pest == "UNKNOWN":
        prepare_unknown(args)
        return

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

    # Whole, realistically-framed negatives from unknown_negatives/ — same
    # fix as UNKNOWN's (see prepare_unknown's docstring): BPH/RSB's negatives
    # were otherwise only ever insect crops (the other pest, four unrelated
    # pests) or tiny background patches, never a normal whole photo with no
    # pest in it. Without these, an out-of-distribution photo (a random
    # animal, an empty field) could score a confident false positive — e.g.
    # a beaver photo scoring 100% RSB — because the model had no exposure to
    # "a whole photo, no pest" at all. See the conversation that added this.
    whole_image_negative_dir = crops_tmp_dir / "whole_image_negatives"
    n_whole_negatives = sum(
        extract_whole_images(source, whole_image_negative_dir, prefix=source.name)
        for source in UNKNOWN_WHOLE_IMAGE_NEGATIVE_DIRS
        if source.exists()
    )
    print(f"{pest}: extracted {n_whole_negatives} whole-image negatives from unknown_negatives/")

    pos_counts = distribute_crops(positive_crops_dir, "positive", pest_out_dir)
    for split, n in pos_counts.items():
        summary["positive"][split] += n

    for source_dir in (other_pest_crops_dir, negative_crops_dir, *background_dirs, whole_image_negative_dir):
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

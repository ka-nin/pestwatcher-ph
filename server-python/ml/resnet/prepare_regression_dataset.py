"""Builds the (image, label) training table for any of the three photo-
derived regression targets the BiLSTM-integration redesign needs:

  --pest BPH --target count         hoppers-per-hill (real ground truth
                                     exists: ml/resnet/bph/_annotations.csv)
  --pest BPH --target coverage_pct  hectares-affected proxy (NO real ground
                                     truth anywhere in this repo — synthetic
                                     crop-paste composites only)
  --pest RSB --target damage_pct    dead-heart/white-ear % (NO real ground
                                     truth either — procedural-damage
                                     composites only, wilt+bleach combined)

count is a generalization of prepare_count_dataset.py (kept separate, since
it's the one target with real images to reuse prepare_dataset.py's
split_bucket() for). coverage_pct/damage_pct have nothing real to split
consistently with, so they get their own random 70/15/15 split over the
synthetic pool — every row in val/test for those two targets is therefore
synthetic too, which is a real limitation (see train_regression.py's
docstring for what that means for trusting the resulting metrics).

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.prepare_regression_dataset --pest BPH --target count
    .venv/Scripts/python.exe -m ml.resnet.prepare_regression_dataset --pest BPH --target coverage_pct
    .venv/Scripts/python.exe -m ml.resnet.prepare_regression_dataset --pest RSB --target damage_pct
"""

import argparse
import csv
import random
from pathlib import Path

import pandas as pd

from ml.resnet.prepare_dataset import split_bucket

RESNET_DIR = Path(__file__).resolve().parent
SYNTHETIC_ROOT = RESNET_DIR.parent / "synthetic" / "datasets"

# Which synthetic run(s) feed each (pest, target) combination. damage_pct
# combines both procedural styles (wilt + bleach) into one training set,
# since the deployed model's job is "estimate % damage" regardless of which
# visual symptom it resembles -- more combined variety, not two models.
SYNTHETIC_RUNS = {
    ("BPH", "count"): ["bph_crop-paste"],
    ("BPH", "coverage_pct"): ["bph_crop-paste"],
    ("RSB", "damage_pct"): ["rsb_procedural-damage_wilt", "rsb_procedural-damage_bleach"],
}

REAL_ANNOTATIONS = {
    "BPH": [RESNET_DIR / "bph"],
}

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15


def real_rows(pest: str, target: str) -> list[dict]:
    """Only count has real ground truth -- see module docstring."""
    if target != "count" or pest not in REAL_ANNOTATIONS:
        return []

    rows = []
    for source_dir in REAL_ANNOTATIONS[pest]:
        annotations = pd.read_csv(source_dir / "_annotations.csv")
        counts = annotations.groupby("filename").size()
        for filename, count in counts.items():
            image_path = source_dir / filename
            if not image_path.exists():
                continue
            rows.append(
                {"path": str(image_path.resolve()), "label": float(count),
                 "split": split_bucket(filename), "source": "real"}
            )
    return rows


def synthetic_rows(pest: str, target: str, real_present: bool, rng: random.Random) -> list[dict]:
    label_column = "count" if target == "count" else "coverage_pct"
    rows = []
    for run_name in SYNTHETIC_RUNS[(pest, target)]:
        labels_path = SYNTHETIC_ROOT / run_name / "labels.csv"
        if not labels_path.exists():
            print(f"No synthetic run at {labels_path} -- skipping (run ml.synthetic.generate_coverage_dataset first)")
            continue
        with labels_path.open() as f:
            for record in csv.DictReader(f):
                image_path = SYNTHETIC_ROOT / run_name / "images" / record["filename"]
                rows.append(
                    {"path": str(image_path.resolve()), "label": float(record[label_column]),
                     "source": "synthetic"}
                )

    if real_present:
        # count: real images already supply val/test, so every synthetic
        # row is a train-only augmentation (see train_count.py's docstring
        # for why val/test must stay real-only).
        for row in rows:
            row["split"] = "train"
    else:
        # coverage_pct / damage_pct: nothing real exists to validate
        # against, so the synthetic pool provides its own held-out split.
        # Not shuffling by filename hash here (unlike split_bucket) because
        # these are independently generated composites with no shared
        # source image to leak across splits.
        shuffled = rows[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = int(n * TRAIN_FRACTION)
        n_val = int(n * VAL_FRACTION)
        for i, row in enumerate(shuffled):
            row["split"] = "train" if i < n_train else ("val" if i < n_train + n_val else "test")
        rows = shuffled

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--target", choices=["count", "coverage_pct", "damage_pct"], required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if (args.pest, args.target) not in SYNTHETIC_RUNS:
        raise SystemExit(f"No synthetic source configured for pest={args.pest} target={args.target}")

    out_dir = RESNET_DIR / "datasets" / "processed" / f"{args.pest.lower()}_{args.target}"
    out_dir.mkdir(parents=True, exist_ok=True)

    real = real_rows(args.pest, args.target)
    synthetic = synthetic_rows(args.pest, args.target, real_present=bool(real), rng=random.Random(args.seed))
    rows = real + synthetic
    if not rows:
        raise SystemExit("No data found at all -- check real annotations / synthetic generation ran first")

    by_split: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for row in rows:
        by_split[row["split"]].append(row)

    for split, split_rows in by_split.items():
        out_path = out_dir / f"{split}.csv"
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "label", "source"])
            writer.writeheader()
            for row in split_rows:
                writer.writerow({"path": row["path"], "label": row["label"], "source": row["source"]})

        n_real = sum(1 for r in split_rows if r["source"] == "real")
        n_synth = sum(1 for r in split_rows if r["source"] == "synthetic")
        print(f"{split}: {len(split_rows)} rows ({n_real} real, {n_synth} synthetic) -> {out_path}")

    if not real:
        print("NOTE: no real ground truth exists for this target -- val/test above are 100% synthetic. "
              "These metrics measure fit to the synthetic generator, not real-photo accuracy.")


if __name__ == "__main__":
    main()

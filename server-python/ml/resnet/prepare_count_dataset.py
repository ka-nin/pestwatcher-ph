"""Builds the (image, count) training table for the BPH hoppers-per-hill
counter (train_count.py) — a different task from prepare_dataset.py's
crop-then-classify pipeline, so it needs a different label: not "is this
crop BPH, yes/no" but "how many BPH are in this whole photo".

Real labels come straight from the annotation file already used elsewhere
in this pipeline: every row in ml/resnet/bph/_annotations.csv is one
bounding box, so counting rows per filename gives the exact true count for
that photo — no separate counting effort, no new annotation needed.

Real counts alone are only ~498 images (see module docstring in
train_count.py for why that's too few on its own), so this also mixes in
ml/synthetic/generate_coverage_dataset.py's crop-paste output, which already
carries an exact, known count per generated image. Synthetic rows are
TRAIN-ONLY — val/test stay 100% real so evaluation reflects real-photo
performance, not how well the model fits its own synthetic generator (see
the "testing" discussion this pipeline is a result of: training on
synthetic, judging only on real).

Uses prepare_dataset.py's own split_bucket() for the real images, so a BPH
photo lands in the same split here as it does in the presence classifier's
dataset — keeps the two pipelines' train/val/test boundaries consistent
rather than letting the same source photo end up in one model's train set
and another model's test set.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.prepare_count_dataset
"""

import csv
from pathlib import Path

import pandas as pd

from ml.resnet.prepare_dataset import split_bucket

RESNET_DIR = Path(__file__).resolve().parent
BPH_DIR = RESNET_DIR / "bph"
SYNTHETIC_DIR = RESNET_DIR.parent / "synthetic" / "datasets" / "bph_crop-paste"
OUT_DIR = RESNET_DIR / "datasets" / "processed" / "bph_count"


def real_rows() -> list[dict]:
    annotations = pd.read_csv(BPH_DIR / "_annotations.csv")
    counts = annotations.groupby("filename").size()

    rows = []
    for filename, count in counts.items():
        image_path = BPH_DIR / filename
        if not image_path.exists():
            continue  # annotation referencing an image that isn't in this export
        rows.append(
            {"path": str(image_path.resolve()), "count": int(count), "split": split_bucket(filename), "source": "real"}
        )
    return rows


def synthetic_rows() -> list[dict]:
    labels_path = SYNTHETIC_DIR / "labels.csv"
    if not labels_path.exists():
        print(f"No synthetic dataset found at {labels_path} — run ml.synthetic.generate_coverage_dataset first "
              "if you want synthetic rows mixed in. Continuing with real data only.")
        return []

    rows = []
    with labels_path.open() as f:
        for record in csv.DictReader(f):
            image_path = SYNTHETIC_DIR / "images" / record["filename"]
            rows.append(
                {"path": str(image_path.resolve()), "count": int(record["count"]), "split": "train", "source": "synthetic"}
            )
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = real_rows() + synthetic_rows()

    by_split: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for row in rows:
        by_split[row["split"]].append(row)

    for split, split_rows in by_split.items():
        out_path = OUT_DIR / f"{split}.csv"
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "count", "source"])
            writer.writeheader()
            for row in split_rows:
                writer.writerow({"path": row["path"], "count": row["count"], "source": row["source"]})

        n_real = sum(1 for r in split_rows if r["source"] == "real")
        n_synth = sum(1 for r in split_rows if r["source"] == "synthetic")
        print(f"{split}: {len(split_rows)} rows ({n_real} real, {n_synth} synthetic) -> {out_path}")


if __name__ == "__main__":
    main()

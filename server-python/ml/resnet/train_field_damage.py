"""Trains the FIELD-level damage regressor on labelled CELLS: a cell in, the
share of that cell covered by damage (0 to 100) out. One model per pest.

Why cells: damage such as whiteheads is thin, and shrinking a whole field photo
to 224 pixels loses it (a whole-photo model read about four times low). Each
photo is cut into an N x N grid of cells, each enlarged, with an exact label
from the generator's mask (ml/synthetic/generate_whitehead_dataset.py). At
serving time the same grid is applied to a field photo, which gives:

  severity  the mean of the cell values (share of the photo covered)
  spread    the share of cells that contain damage (how widely it is spread)
  heatmap   the grid of cell values

Training data is SYNTHETIC (real damage sprites pasted on real healthy field
photos). The synthetic test split shows the model learned its generator; only
REAL photos with a technologist's measured damage mean anything about the
field (ml/resnet/evaluate_real_photos.py).

--backbone makes "why ResNet-50" a like-for-like comparison: same data, head,
schedule and splits.

Run from server-python/ (needs SSL_CERT_FILE set to certifi's bundle on a
python.org Python so ImageNet weights can download):
    .venv/bin/python -m ml.resnet.train_field_damage --pest RSB --backbone efficientnetb0
    .venv/bin/python -m ml.resnet.train_field_damage --pest RSB --backbone resnet50 --no-save
"""

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import efficientnet, resnet50

from ml.config import WEIGHTS_DIR

DATASETS = Path(__file__).resolve().parent.parent / "synthetic" / "datasets"
PEST_DATASETS = {"RSB": DATASETS / "rsb_whitehead_sim", "BPH": DATASETS / "bph_hopperburn_sim"}
DATA_DIR = PEST_DATASETS["RSB"]
BATCH_SIZE = 32
CELL_AFFECTED_MIN_PCT = 0.2  # a cell "has damage" when at least this share of it is covered

BACKBONES = {
    "resnet50": (lambda size: resnet50.ResNet50(include_top=False, weights="imagenet", input_shape=(size, size, 3), pooling="avg"), resnet50.preprocess_input, 143),
    # EfficientNet rescales inside the model: its keras preprocess_input is the identity.
    "efficientnetb0": (lambda size: efficientnet.EfficientNetB0(include_top=False, weights="imagenet", input_shape=(size, size, 3), pooling="avg"), efficientnet.preprocess_input, 200),
}


def read_split(pest: str, split: str) -> list[dict]:
    rows = []
    with (DATA_DIR / "cell_labels.csv").open() as f:
        for r in csv.DictReader(f):
            if r["split"] == split:
                rows.append({"path": str(DATA_DIR / "cells" / r["filename"]), "label": float(r["coverage_pct"]),
                             "image": r["image"], "row": int(r["row"]), "col": int(r["col"])})
    return rows


def make_ds(rows: list[dict], size: int, preprocess, training: bool):
    def load(path, label):
        img = tf.image.resize(tf.image.decode_jpeg(tf.io.read_file(path), channels=3), (size, size))
        return img, label

    ds = tf.data.Dataset.from_tensor_slices(([r["path"] for r in rows], [r["label"] for r in rows]))
    if training:
        ds = ds.shuffle(len(rows), seed=42)
    ds = ds.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(BATCH_SIZE)
    aug = keras.Sequential([layers.RandomFlip("horizontal_and_vertical"), layers.RandomBrightness(0.1), layers.RandomContrast(0.1)])
    return ds.map(lambda x, y: (preprocess(aug(x) if training else x), y)).prefetch(tf.data.AUTOTUNE)


def build(backbone_name: str, size: int):
    factory, _, _ = BACKBONES[backbone_name]
    backbone = factory(size)
    backbone.trainable = False
    inputs = keras.Input(shape=(size, size, 3))
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(1, activation="relu", name="field_damage_pct")(x)
    return keras.Model(inputs, out), backbone


def regression_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    err = p - y
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {"rmse": float(np.sqrt(np.mean(err**2))), "mae": float(np.mean(np.abs(err))),
            "r2": 1 - float(np.sum(err**2)) / ss_tot if ss_tot > 0 else float("nan"), "n": int(len(y))}


def predict(model, rows, size, preprocess) -> np.ndarray:
    return model.predict(make_ds(rows, size, preprocess, False), verbose=0).flatten()


def best_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Prediction threshold that maximises F1 for 'this cell has damage' on validation data."""
    truth = y >= CELL_AFFECTED_MIN_PCT
    best, best_f1 = 0.2, -1.0
    for t in np.arange(0.05, 2.0, 0.05):
        pred = p >= t
        tp = float(np.sum(pred & truth))
        prec, rec = tp / max(pred.sum(), 1), tp / max(truth.sum(), 1)
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        if f1 > best_f1:
            best, best_f1 = float(t), f1
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    ap.add_argument("--backbone", choices=list(BACKBONES), default="resnet50")
    ap.add_argument("--input-size", type=int, default=160)
    ap.add_argument("--head-epochs", type=int, default=12)
    ap.add_argument("--fine-tune-epochs", type=int, default=20)
    ap.add_argument("--data-dir", type=Path, default=None, help="default: the pest's own dataset under ml/synthetic/datasets")
    ap.add_argument("--no-save", action="store_true", help="evaluate only; do not install the model")
    args = ap.parse_args()

    global DATA_DIR
    DATA_DIR = args.data_dir or PEST_DATASETS[args.pest]
    size = args.input_size
    _, preprocess, unfreeze_from = BACKBONES[args.backbone]
    splits = {s: read_split(args.pest, s) for s in ("train", "val", "test")}
    print({s: len(v) for s, v in splits.items()}, "cells")
    train, val = make_ds(splits["train"], size, preprocess, True), make_ds(splits["val"], size, preprocess, False)

    model, backbone = build(args.backbone, size)
    stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
    t0 = time.time()
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="mse", metrics=["mae"])
    model.fit(train, validation_data=val, epochs=args.head_epochs, callbacks=[stop], verbose=2)
    backbone.trainable = True
    for layer in backbone.layers[:unfreeze_from]:
        layer.trainable = False
    model.compile(optimizer=keras.optimizers.Adam(1e-5), loss="mse", metrics=["mae"])
    model.fit(train, validation_data=val, epochs=args.fine_tune_epochs, callbacks=[stop], verbose=2)
    seconds = round(time.time() - t0, 1)

    yv = np.array([r["label"] for r in splits["val"]])
    threshold = best_threshold(yv, predict(model, splits["val"], size, preprocess))

    test_rows = splits["test"]
    y = np.array([r["label"] for r in test_rows])
    p = predict(model, test_rows, size, preprocess)
    by_image = defaultdict(list)
    for r, truth, pred in zip(test_rows, y, p):
        by_image[r["image"]].append((truth, pred))
    img_true = np.array([np.mean([t for t, _ in v]) for v in by_image.values()])
    img_pred = np.array([np.mean([q for _, q in v]) for v in by_image.values()])
    spread_true = np.array([np.mean([t >= CELL_AFFECTED_MIN_PCT for t, _ in v]) for v in by_image.values()]) * 100
    spread_pred = np.array([np.mean([q >= threshold for _, q in v]) for v in by_image.values()]) * 100
    truth_c, pred_c = y >= CELL_AFFECTED_MIN_PCT, p >= threshold
    tp = float(np.sum(truth_c & pred_c))

    result = {
        "pest": args.pest, "backbone": args.backbone, "input_size": size, "train_seconds": seconds,
        "parameters": int(model.count_params()), "test_set_is_synthetic": True,
        "cell": regression_metrics(y, p),
        "image_severity": regression_metrics(img_true, img_pred),
        "image_severity_baseline_mae_predict_mean": float(np.mean(np.abs(img_true - img_true.mean()))),
        "image_spread_pct_of_cells": regression_metrics(spread_true, spread_pred),
        "cell_has_damage": {"threshold": threshold, "label_min_pct": CELL_AFFECTED_MIN_PCT,
                            "precision": tp / max(pred_c.sum(), 1), "recall": tp / max(truth_c.sum(), 1)},
    }
    print(json.dumps(result, indent=2))
    out_dir = WEIGHTS_DIR / args.pest.lower()
    (out_dir / f"field_damage_{args.pest.lower()}_{args.backbone}_synthetic_test_metrics.json").write_text(json.dumps(result, indent=2))
    if not args.no_save:
        model.save(out_dir / f"resnet50_{args.pest.lower()}_field_damage_pct.keras")  # filename fixed by the serving code
        (out_dir / f"resnet50_{args.pest.lower()}_field_damage_pct.meta.json").write_text(json.dumps({
            "backbone": args.backbone, "input_size": size, "grid": 3,
            "cell_has_damage_threshold": threshold, "cell_label_min_pct": CELL_AFFECTED_MIN_PCT}, indent=2))
        print("installed model + meta")


if __name__ == "__main__":
    main()

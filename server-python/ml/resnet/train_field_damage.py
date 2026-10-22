"""Trains the FIELD-level damage regressor: whole-field photo in, % of the
photo showing damage out. One model per pest.

Training data is synthetic (ml/synthetic/generate_field_damage_dataset.py:
damage painted onto real healthy field photos, label = mask area). Test data
that means anything is REAL photos with a technologist's measured damage %:
score the saved model with ml/resnet/evaluate_real_photos.py. The synthetic
test split printed here only shows the model learned its generator.

--backbone selects the feature extractor so the panel's "why ResNet-50" can be
answered with a like-for-like comparison: same data, head, schedule and splits.

Run from server-python/:
    .venv/bin/python -m ml.resnet.train_field_damage --pest BPH
    .venv/bin/python -m ml.resnet.train_field_damage --pest BPH --backbone efficientnetb0
"""

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import efficientnet, resnet50

from ml.config import WEIGHTS_DIR

DATA_DIR = Path(__file__).resolve().parent.parent / "synthetic" / "datasets" / "field_damage_sim"
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
HEAD_EPOCHS = 15
FINE_TUNE_EPOCHS = 20

BACKBONES = {
    "resnet50": (lambda: resnet50.ResNet50(include_top=False, weights="imagenet", input_shape=(*IMAGE_SIZE, 3), pooling="avg"), resnet50.preprocess_input, 143),
    # EfficientNet's keras preprocess is the identity (it rescales inside the model).
    "efficientnetb0": (lambda: efficientnet.EfficientNetB0(include_top=False, weights="imagenet", input_shape=(*IMAGE_SIZE, 3), pooling="avg"), efficientnet.preprocess_input, 200),
}


def read_split(pest: str, split: str) -> tuple[list[str], list[float]]:
    paths, labels = [], []
    with (DATA_DIR / "labels.csv").open() as f:
        for row in csv.DictReader(f):
            if row["split"] != split:
                continue
            # Negatives carry no pest meaning (damage 0), so both models learn them.
            if row["pest"] != pest and not row["mode"].startswith("negative"):
                continue
            paths.append(str(DATA_DIR / "images" / row["filename"]))
            labels.append(float(row["coverage_pct"]))
    return paths, labels


def make_ds(paths, labels, preprocess, training):
    def load(path, label):
        img = tf.image.resize(tf.image.decode_jpeg(tf.io.read_file(path), channels=3), IMAGE_SIZE)
        return img, label

    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    if training:
        ds = ds.shuffle(len(paths), seed=42)
    ds = ds.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(BATCH_SIZE)
    aug = keras.Sequential([layers.RandomFlip("horizontal"), layers.RandomBrightness(0.1), layers.RandomContrast(0.1)])
    return ds.map(lambda x, y: (preprocess(aug(x) if training else x), y)).prefetch(tf.data.AUTOTUNE)


def build(backbone_name: str):
    factory, _, _ = BACKBONES[backbone_name]
    backbone = factory()
    backbone.trainable = False
    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(1, activation="relu", name="field_damage_pct")(x)
    return keras.Model(inputs, out), backbone


def metrics(model, ds) -> dict:
    y = np.concatenate([b[1].numpy() for b in ds]).flatten()
    p = model.predict(ds, verbose=0).flatten()
    err = p - y
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {"rmse": float(np.sqrt(np.mean(err**2))), "mae": float(np.mean(np.abs(err))),
            "r2": 1 - float(np.sum(err**2)) / ss_tot if ss_tot > 0 else float("nan"), "n": int(len(y))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    ap.add_argument("--backbone", choices=list(BACKBONES), default="resnet50")
    ap.add_argument("--head-epochs", type=int, default=HEAD_EPOCHS)
    ap.add_argument("--fine-tune-epochs", type=int, default=FINE_TUNE_EPOCHS)
    ap.add_argument("--no-save", action="store_true", help="evaluate only; do not overwrite the deployed weights")
    args = ap.parse_args()

    _, preprocess, unfreeze_from = BACKBONES[args.backbone]
    sets = {s: read_split(args.pest, s) for s in ("train", "val", "test")}
    print({s: len(v[0]) for s, v in sets.items()})
    if not sets["test"][0] or not sets["val"][0]:
        raise SystemExit("val/test split is empty: the split is by background photo, so it needs many background photos.")
    train, val, test = (make_ds(*sets[s], preprocess, s == "train") for s in ("train", "val", "test"))

    model, backbone = build(args.backbone)
    stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
    t0 = time.time()
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="mse", metrics=["mae"])
    model.fit(train, validation_data=val, epochs=args.head_epochs, callbacks=[stop], verbose=2)
    backbone.trainable = True
    for layer in backbone.layers[:unfreeze_from]:
        layer.trainable = False
    model.compile(optimizer=keras.optimizers.Adam(1e-5), loss="mse", metrics=["mae"])
    model.fit(train, validation_data=val, epochs=args.fine_tune_epochs, callbacks=[stop], verbose=2)

    result = metrics(model, test)
    result.update(pest=args.pest, backbone=args.backbone, train_seconds=round(time.time() - t0, 1),
                  parameters=int(model.count_params()), test_set_is_synthetic=True)
    print(json.dumps(result, indent=2))
    out_dir = WEIGHTS_DIR / args.pest.lower()
    (out_dir / f"field_damage_{args.pest.lower()}_{args.backbone}_synthetic_test_metrics.json").write_text(json.dumps(result, indent=2))
    if not args.no_save and args.backbone == "resnet50":
        model.save(out_dir / f"resnet50_{args.pest.lower()}_field_damage_pct.keras")
        print("saved deployable model")


if __name__ == "__main__":
    main()

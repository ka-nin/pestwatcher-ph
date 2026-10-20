"""Trains the BPH hoppers-per-hill counter — a ResNet-50 regression model
that predicts how many BPH are visible in a photo, instead of the existing
resnet50_bph.keras's yes/no presence classification.

This is a genuinely different task from the rest of ml/resnet/: a single
sigmoid output can't express "how many", so the head here ends in one
relu-activated unit (count can't be negative) trained with MSE, the same
loss family ml/bilstm/train.py already uses for its own continuous target.
Architecture and transfer-learning schedule otherwise mirror train.py
exactly (frozen-backbone phase, then partial fine-tune) — same backbone,
same two-phase recipe, different head and loss for a different kind of
target.

Why real images alone aren't enough: ml/resnet/bph/_annotations.csv only
covers 498 photos. A regression head needs to see count vary across many
photos to learn the relationship between "how cluttered this looks" and
"how many insects" — 498 is thin for that, so ml/resnet/prepare_count_dataset.py
mixes in synthetic crop-paste composites (exact known counts, generated
from real crops and real backgrounds) for the TRAIN split only. Validation
and test stay 100% real, so the numbers below answer "how good is this on
actual farmer photos", not "how well did it memorize its own generator".

--no-synthetic trains on the real rows only, so you can directly compare
against the default (real+synthetic) run on the identical real test set —
the same before/after comparison this project already uses elsewhere to
justify a design choice with numbers instead of assertion.

Run from server-python/ (after ml.resnet.prepare_count_dataset):
    .venv/Scripts/python.exe -m ml.resnet.train_count
    .venv/Scripts/python.exe -m ml.resnet.train_count --no-synthetic
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import resnet50

from ml.config import WEIGHTS_DIR

PROCESSED_DIR = Path(__file__).resolve().parent / "datasets" / "processed" / "bph_count"

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
HEAD_EPOCHS = 15
FINE_TUNE_EPOCHS = 20
FINE_TUNE_UNFREEZE_FROM = 143  # same cutoff as ml/resnet/train.py, same backbone


def _read_rows(split: str, include_synthetic: bool) -> tuple[list[str], list[float]]:
    csv_path = PROCESSED_DIR / f"{split}.csv"
    if not csv_path.exists():
        raise SystemExit(f"{csv_path} not found — run ml.resnet.prepare_count_dataset first")

    paths, counts = [], []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            if row["source"] == "synthetic" and not include_synthetic:
                continue
            paths.append(row["path"])
            counts.append(float(row["count"]))
    return paths, counts


def _make_dataset(paths: list[str], counts: list[float], shuffle: bool) -> tf.data.Dataset:
    def load(path, count):
        image = tf.io.read_file(path)
        image = tf.image.decode_jpeg(image, channels=3)
        image = tf.image.resize(image, IMAGE_SIZE)
        return image, count

    ds = tf.data.Dataset.from_tensor_slices((paths, counts))
    if shuffle:
        ds = ds.shuffle(buffer_size=len(paths), seed=42)
    ds = ds.map(load, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.batch(BATCH_SIZE)


def load_datasets(include_synthetic: bool) -> tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset]:
    train_paths, train_counts = _read_rows("train", include_synthetic)
    val_paths, val_counts = _read_rows("val", include_synthetic=False)  # val/test always real-only
    test_paths, test_counts = _read_rows("test", include_synthetic=False)

    print(f"train: {len(train_paths)} images, val: {len(val_paths)}, test: {len(test_paths)} (val/test always real)")

    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.15),
            layers.RandomBrightness(0.1),
            layers.RandomContrast(0.1),
        ],
        name="augmentation",
    )

    def preprocess(images, counts, training: bool):
        if training:
            images = augmentation(images)
        images = resnet50.preprocess_input(images)
        return images, counts

    train_ds = _make_dataset(train_paths, train_counts, shuffle=True).map(
        lambda x, y: preprocess(x, y, training=True)
    ).prefetch(tf.data.AUTOTUNE)
    val_ds = _make_dataset(val_paths, val_counts, shuffle=False).map(
        lambda x, y: preprocess(x, y, training=False)
    ).prefetch(tf.data.AUTOTUNE)
    test_ds = _make_dataset(test_paths, test_counts, shuffle=False).map(
        lambda x, y: preprocess(x, y, training=False)
    ).prefetch(tf.data.AUTOTUNE)

    return train_ds, val_ds, test_ds


def build_model() -> tuple[keras.Model, keras.Model]:
    backbone = resnet50.ResNet50(include_top=False, weights="imagenet", input_shape=(*IMAGE_SIZE, 3), pooling="avg")
    backbone.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.Dropout(0.3)(x)
    # relu, not linear/sigmoid: a predicted count below zero is meaningless,
    # and counts aren't bounded at 1 the way a presence classifier's output is.
    output = layers.Dense(1, activation="relu", name="count")(x)

    model = keras.Model(inputs, output)
    return model, backbone


def evaluate(model: keras.Model, test_ds: tf.data.Dataset) -> dict:
    y_true = np.concatenate([y.numpy() for _, y in test_ds]).flatten()
    y_pred = model.predict(test_ds, verbose=0).flatten()

    errors = y_pred - y_true
    rmse = float(np.sqrt(np.mean(errors**2)))
    mae = float(np.mean(np.abs(errors)))
    ss_res = float(np.sum(errors**2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "mean_actual_count": float(y_true.mean()),
        "n_test_images": int(len(y_true)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-synthetic", action="store_true", help="train on real BPH photos only, no synthetic composites")
    args = parser.parse_args()
    include_synthetic = not args.no_synthetic

    train_ds, val_ds, test_ds = load_datasets(include_synthetic)

    model, backbone = build_model()
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
        metrics=["mae"],
    )
    model.summary()

    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

    print(f"\n--- Phase 1: training head only ({HEAD_EPOCHS} epochs max) ---")
    model.fit(train_ds, validation_data=val_ds, epochs=HEAD_EPOCHS, callbacks=[early_stopping], verbose=2)

    print(f"\n--- Phase 2: fine-tuning from layer {FINE_TUNE_UNFREEZE_FROM} ({FINE_TUNE_EPOCHS} epochs max) ---")
    backbone.trainable = True
    for layer in backbone.layers[:FINE_TUNE_UNFREEZE_FROM]:
        layer.trainable = False

    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-5), loss="mse", metrics=["mae"])
    model.fit(train_ds, validation_data=val_ds, epochs=FINE_TUNE_EPOCHS, callbacks=[early_stopping], verbose=2)

    test_metrics = evaluate(model, test_ds)
    test_metrics["trained_with_synthetic"] = include_synthetic
    print("\nTest metrics (real photos only):", json.dumps(test_metrics, indent=2))

    weights_path = WEIGHTS_DIR / "bph" / "resnet50_bph_count.keras"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(weights_path)

    suffix = "" if include_synthetic else "_no_synthetic"
    metrics_path = weights_path.parent / f"resnet50_bph_count_test_metrics{suffix}.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))

    print(f"Saved model to {weights_path}")
    print(f"Saved test metrics to {metrics_path}")


if __name__ == "__main__":
    main()

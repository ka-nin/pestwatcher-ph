"""Trains a ResNet-50 regression head for one of the three photo-derived
inputs the BiLSTM-integration redesign needs: BPH hoppers-per-hill (count),
BPH hectares-affected proxy (coverage_pct), or RSB damage % (damage_pct).

Same architecture and two-phase transfer-learning schedule as train.py and
train_count.py (frozen backbone, then partial fine-tune) -- only the target
column and, for coverage_pct/damage_pct, the complete absence of real test
data changes.

IMPORTANT, read before trusting coverage_pct/damage_pct numbers: unlike
count (which has 498 real annotated photos backing its val/test split),
coverage_pct and damage_pct have ZERO real images anywhere in this project
with a known coverage or damage percentage. Their train/val/test are ALL
synthetic. A good test RMSE/MAE/R2 for those two targets proves the model
can recover the number IT ITSELF composited the image from -- it says
nothing about accuracy on an actual farmer photo. That can only be checked
the way the project's own testing plan already described: real photos,
judged by a human (technologist) estimate, compared against the model's
output. Report coverage_pct/damage_pct metrics as "synthetic self-
consistency", not as real-world accuracy, until that real-photo check runs.

Run from server-python/ (after ml.resnet.prepare_regression_dataset):
    .venv/Scripts/python.exe -m ml.resnet.train_regression --pest BPH --target count
    .venv/Scripts/python.exe -m ml.resnet.train_regression --pest BPH --target coverage_pct
    .venv/Scripts/python.exe -m ml.resnet.train_regression --pest RSB --target damage_pct
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

PROCESSED_DIR = Path(__file__).resolve().parent / "datasets" / "processed"

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
HEAD_EPOCHS = 15
FINE_TUNE_EPOCHS = 20
FINE_TUNE_UNFREEZE_FROM = 143


def _read_rows(processed_dir: Path, split: str, include_synthetic: bool) -> tuple[list[str], list[float]]:
    csv_path = processed_dir / f"{split}.csv"
    if not csv_path.exists():
        raise SystemExit(f"{csv_path} not found -- run ml.resnet.prepare_regression_dataset first")

    paths, labels = [], []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            if row["source"] == "synthetic" and not include_synthetic:
                continue
            paths.append(row["path"])
            labels.append(float(row["label"]))
    return paths, labels


def _make_dataset(paths: list[str], labels: list[float], shuffle: bool) -> tf.data.Dataset:
    def load(path, label):
        image = tf.io.read_file(path)
        image = tf.image.decode_jpeg(image, channels=3)
        image = tf.image.resize(image, IMAGE_SIZE)
        return image, label

    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    if shuffle:
        ds = ds.shuffle(buffer_size=max(1, len(paths)), seed=42)
    ds = ds.map(load, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.batch(BATCH_SIZE)


def load_datasets(processed_dir: Path, include_synthetic: bool) -> tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset, bool]:
    train_paths, train_labels = _read_rows(processed_dir, "train", include_synthetic)
    val_paths, val_labels = _read_rows(processed_dir, "val", include_synthetic=False)
    test_paths, test_labels = _read_rows(processed_dir, "test", include_synthetic=False)

    # include_synthetic=False on val/test means "exclude synthetic ONLY IF
    # real rows exist" in the count case; for coverage_pct/damage_pct every
    # row IS synthetic, so that filter would silently empty the split. Fall
    # back to the full (synthetic) split when no real rows are present.
    if not val_paths:
        val_paths, val_labels = _read_rows(processed_dir, "val", include_synthetic=True)
    if not test_paths:
        test_paths, test_labels = _read_rows(processed_dir, "test", include_synthetic=True)

    test_is_synthetic = all(
        row["source"] == "synthetic"
        for row in csv.DictReader((processed_dir / "test.csv").open())
    )

    print(f"train: {len(train_paths)} images, val: {len(val_paths)}, test: {len(test_paths)} "
          f"({'SYNTHETIC-ONLY' if test_is_synthetic else 'real'})")

    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.15),
            layers.RandomBrightness(0.1),
            layers.RandomContrast(0.1),
        ],
        name="augmentation",
    )

    def preprocess(images, labels, training: bool):
        if training:
            images = augmentation(images)
        images = resnet50.preprocess_input(images)
        return images, labels

    train_ds = _make_dataset(train_paths, train_labels, shuffle=True).map(
        lambda x, y: preprocess(x, y, training=True)
    ).prefetch(tf.data.AUTOTUNE)
    val_ds = _make_dataset(val_paths, val_labels, shuffle=False).map(
        lambda x, y: preprocess(x, y, training=False)
    ).prefetch(tf.data.AUTOTUNE)
    test_ds = _make_dataset(test_paths, test_labels, shuffle=False).map(
        lambda x, y: preprocess(x, y, training=False)
    ).prefetch(tf.data.AUTOTUNE)

    return train_ds, val_ds, test_ds, test_is_synthetic


def build_model() -> tuple[keras.Model, keras.Model]:
    backbone = resnet50.ResNet50(include_top=False, weights="imagenet", input_shape=(*IMAGE_SIZE, 3), pooling="avg")
    backbone.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.Dropout(0.3)(x)
    output = layers.Dense(1, activation="relu", name="regression_output")(x)  # non-negative: count and % both are

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

    return {"rmse": rmse, "mae": mae, "r2": r2, "mean_actual_label": float(y_true.mean()), "n_test_images": int(len(y_true))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--target", choices=["count", "coverage_pct", "damage_pct"], required=True)
    parser.add_argument("--no-synthetic", action="store_true")
    args = parser.parse_args()
    include_synthetic = not args.no_synthetic

    processed_dir = PROCESSED_DIR / f"{args.pest.lower()}_{args.target}"
    train_ds, val_ds, test_ds, test_is_synthetic = load_datasets(processed_dir, include_synthetic)

    model, backbone = build_model()
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3), loss="mse", metrics=["mae"])
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
    test_metrics["test_set_is_synthetic"] = test_is_synthetic
    print(f"\nTest metrics ({'SYNTHETIC-ONLY -- see module docstring' if test_is_synthetic else 'real photos only'}):",
          json.dumps(test_metrics, indent=2))

    weights_path = WEIGHTS_DIR / args.pest.lower() / f"resnet50_{args.pest.lower()}_{args.target}.keras"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(weights_path)

    suffix = "" if include_synthetic else "_no_synthetic"
    metrics_path = weights_path.parent / f"resnet50_{args.pest.lower()}_{args.target}_test_metrics{suffix}.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))

    print(f"Saved model to {weights_path}")
    print(f"Saved test metrics to {metrics_path}")


if __name__ == "__main__":
    main()

"""Trains a binary ResNet-50 pest classifier for one pest (BPH or RSB) on
the crops from ml/resnet/prepare_dataset.py.

Architecture: an ImageNet-pretrained ResNet-50 backbone (frozen initially,
then partially unfrozen for fine-tuning) with a small dense binary head.
Transfer learning rather than training from scratch, since the dataset here
(a few thousand crops) is far smaller than what ResNet-50 needs to learn
useful visual features on its own — ImageNet's general-purpose features
(edges, textures, shapes) are a much better starting point.

Two-phase training:
  1. Head-only: backbone frozen, train just the new dense head. Lets the
     randomly-initialized head settle without back-propagating large,
     destructive gradients into the pretrained backbone.
  2. Fine-tune: unfreeze the backbone's last block and continue training
     both together at a much lower learning rate, so the backbone's
     general ImageNet features adapt slightly toward pest-crop-specific
     ones without being overwritten wholesale.

Class weighting (not resampling) handles the positive/negative imbalance —
see ml/resnet/prepare_dataset.py's docstring for why negatives include both
the other target pest and four unrelated rice pests, which makes negatives
outnumber positives several times over for both pests.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.resnet.train --pest BPH
    .venv/Scripts/python.exe -m ml.resnet.train --pest RSB
"""

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import resnet50

from ml.config import PEST_PARAMS

RESNET_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = RESNET_DIR / "datasets" / "processed"

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
HEAD_EPOCHS = 15
FINE_TUNE_EPOCHS = 20
FINE_TUNE_UNFREEZE_FROM = 143  # ResNet-50 has 175 layers; unfreezes roughly the last block


def load_datasets(pest_dir: Path) -> tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset, dict[int, float]]:
    """class_names is sorted alphabetically by keras -> ["negative", "positive"],
    so class index 1 is always "positive" here; label smoothing/weighting below
    relies on that order."""

    def make_dataset(split: str, shuffle: bool) -> tf.data.Dataset:
        return keras.utils.image_dataset_from_directory(
            pest_dir / split,
            labels="inferred",
            label_mode="binary",
            class_names=["negative", "positive"],
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            shuffle=shuffle,
            seed=42,
        )

    train_ds = make_dataset("train", shuffle=True)
    val_ds = make_dataset("val", shuffle=False)
    test_ds = make_dataset("test", shuffle=False)

    n_positive = len(list((pest_dir / "train" / "positive").glob("*.jpg")))
    n_negative = len(list((pest_dir / "train" / "negative").glob("*.jpg")))
    total = n_positive + n_negative
    # Inverse-frequency weighting: rarer class gets a proportionally larger
    # weight so the loss doesn't just learn to always predict "negative".
    class_weight = {
        0: total / (2 * n_negative),
        1: total / (2 * n_positive),
    }

    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.15),
            layers.RandomBrightness(0.1),
            layers.RandomContrast(0.1),
        ],
        name="augmentation",
    )

    def preprocess(images, labels, training: bool) -> tuple[tf.Tensor, tf.Tensor]:
        if training:
            images = augmentation(images)
        images = resnet50.preprocess_input(images)
        return images, labels

    train_ds = train_ds.map(lambda x, y: preprocess(x, y, training=True)).prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.map(lambda x, y: preprocess(x, y, training=False)).prefetch(tf.data.AUTOTUNE)
    test_ds = test_ds.map(lambda x, y: preprocess(x, y, training=False)).prefetch(tf.data.AUTOTUNE)

    return train_ds, val_ds, test_ds, class_weight


def build_model() -> tuple[keras.Model, keras.Model]:
    """Returns (model, backbone) — the caller needs the backbone separately
    to toggle its trainable layers between phase 1 and phase 2."""
    backbone = resnet50.ResNet50(include_top=False, weights="imagenet", input_shape=(*IMAGE_SIZE, 3), pooling="avg")
    backbone.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = backbone(inputs, training=False)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.Dropout(0.3)(x)
    output = layers.Dense(1, activation="sigmoid", name="prediction")(x)

    model = keras.Model(inputs, output)
    return model, backbone


def evaluate(model: keras.Model, test_ds: tf.data.Dataset) -> dict:
    y_true = np.concatenate([y.numpy() for _, y in test_ds]).flatten()
    y_prob = model.predict(test_ds, verbose=0).flatten()
    y_pred = (y_prob >= 0.5).astype(int)

    report = classification_report(y_true, y_pred, target_names=["negative", "positive"], output_dict=True)
    cm = confusion_matrix(y_true, y_pred).tolist()

    return {
        "accuracy": report["accuracy"],
        "positive_precision": report["positive"]["precision"],
        "positive_recall": report["positive"]["recall"],
        "positive_f1": report["positive"]["f1-score"],
        "confusion_matrix": cm,
        "confusion_matrix_labels": ["negative", "positive"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = parser.parse_args()

    pest = args.pest
    pest_dir = PROCESSED_DIR / pest.lower()
    if not pest_dir.exists():
        raise SystemExit(f"{pest_dir} not found — run ml.resnet.prepare_dataset --pest {pest} first")

    train_ds, val_ds, test_ds, class_weight = load_datasets(pest_dir)
    print(f"{pest}: class weights = {class_weight}")

    model, backbone = build_model()
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.Precision(name="precision"), keras.metrics.Recall(name="recall")],
    )
    model.summary()

    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

    print(f"\n--- Phase 1: training head only ({HEAD_EPOCHS} epochs max) ---")
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=HEAD_EPOCHS,
        class_weight=class_weight,
        callbacks=[early_stopping],
        verbose=2,
    )

    print(f"\n--- Phase 2: fine-tuning from layer {FINE_TUNE_UNFREEZE_FROM} ({FINE_TUNE_EPOCHS} epochs max) ---")
    backbone.trainable = True
    for layer in backbone.layers[:FINE_TUNE_UNFREEZE_FROM]:
        layer.trainable = False

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-5),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.Precision(name="precision"), keras.metrics.Recall(name="recall")],
    )
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=FINE_TUNE_EPOCHS,
        class_weight=class_weight,
        callbacks=[early_stopping],
        verbose=2,
    )

    test_metrics = evaluate(model, test_ds)
    print(f"\n{pest} test metrics:", json.dumps(test_metrics, indent=2))

    weights_path = PEST_PARAMS[pest].resnet_weights_path
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(weights_path)

    metrics_path = weights_path.parent / f"resnet50_{pest.lower()}_test_metrics.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))

    print(f"Saved model to {weights_path}")
    print(f"Saved test metrics to {metrics_path}")


if __name__ == "__main__":
    main()

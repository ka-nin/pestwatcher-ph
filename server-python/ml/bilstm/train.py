"""Trains the BiLSTM outbreak forecaster for one pest (BPH or RSB) on the
sequences from ml/bilstm/build_sequences.py.

Architecture: a Bidirectional LSTM over the 14-day daily sequence
(Tmax/Tmin/RH/Rainfall/VPD/diurnal range/growth-stage one-hot), concatenated
with the static engineered aggregate vector (GDD/CRF/HP/WSI/trends/
interaction terms), feeding a small dense regression head. Output is a
single continuous value — hoppers/hill for BPH, % damage for RSB — per
fix #1 from the panel: the model learns the forecast, ETL only buckets it
afterward (see app/decision/etl_thresholds.py, not yet written).

Split strategy: chronological, not random. Sequences overlap by 1 day (a
sliding window), so a random shuffle would put near-duplicate windows in
both train and test, leaking information and inflating the reported metrics.
Instead the most recent ~15% of dates become the test set, the ~15% before
that become validation, and a `PURGE_GAP_DAYS`-day buffer is dropped at each
boundary so no train window's target date sits inside a test window's input
window (or vice versa).

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.train --pest BPH
    .venv/Scripts/python.exe -m ml.bilstm.train --pest RSB
"""

import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow import keras
from tensorflow.keras import layers

from ml.bilstm.build_sequences import FEATURE_SET_SUFFIX, sequences_path
from ml.bilstm.etl_metrics import classification_agreement, to_risk_levels
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
# TEST_FRACTION is whatever remains (~0.15)


def load_dataset(
    pest: str, feature_set: str = "engineered"
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame, list[str], list[str]]:
    npz_path, meta_path = sequences_path(pest, feature_set)
    data = np.load(npz_path, allow_pickle=True)
    meta = pd.read_csv(meta_path, parse_dates=["target_date"])
    return (
        data["X_sequence"],
        data["X_static"],
        data["y"],
        meta,
        list(data["sequence_feature_columns"]),
        list(data["static_feature_columns"]),
    )


def chronological_split(meta: pd.DataFrame, window_days: int, horizon_days: int) -> dict[str, np.ndarray]:
    """Returns row indices (into the original arrays) for train/val/test,
    ordered by target_date with a purge gap at each boundary."""
    order = meta["target_date"].sort_values().index.to_numpy()
    n = len(order)

    train_end = int(n * TRAIN_FRACTION)
    val_end = train_end + int(n * VAL_FRACTION)

    purge = window_days + horizon_days  # widest span a single sample can touch

    train_idx = order[: max(train_end - purge, 0)]
    val_idx = order[train_end + purge : max(val_end - purge, train_end + purge)]
    test_idx = order[val_end + purge :]

    return {"train": train_idx, "val": val_idx, "test": test_idx}


def scale_sequence(X_train, X_val, X_test) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    _, window_days, n_features = X_train.shape
    scaler = StandardScaler()
    scaler.fit(X_train.reshape(-1, n_features))

    def transform(X):
        n = X.shape[0]
        return scaler.transform(X.reshape(-1, n_features)).reshape(n, window_days, n_features)

    return transform(X_train), transform(X_val), transform(X_test), scaler


def build_model(window_days: int, n_seq_features: int, n_static_features: int) -> keras.Model:
    """Deliberately small: an earlier, larger version (64/32 LSTM units, no
    L2) overfit within 2 epochs on both pests — val_loss started climbing
    immediately while train_loss kept dropping, meaning the model had far
    more capacity than the ~6 years / 5 municipalities of data could
    support. This version trades capacity for regularization instead.

    `n_static_features == 0` is the raw-feature control from the thesis's RQ2
    (ml/bilstm/build_sequences.py --features raw): there is no static vector
    to merge, so the static branch is dropped and the LSTM output feeds the
    dense head directly. The recurrent core, the head widths, the
    regularization and the optimizer are identical either way, so the
    comparison isolates the features rather than the architecture.
    """
    l2 = keras.regularizers.l2(1e-3)

    sequence_input = keras.Input(shape=(window_days, n_seq_features), name="sequence_input")
    inputs = [sequence_input]

    x = layers.Bidirectional(layers.LSTM(16, kernel_regularizer=l2, recurrent_dropout=0.1))(sequence_input)
    x = layers.Dropout(0.4)(x)

    if n_static_features > 0:
        static_input = keras.Input(shape=(n_static_features,), name="static_input")
        inputs.append(static_input)
        s = layers.Dense(8, activation="relu", kernel_regularizer=l2)(static_input)
        x = layers.Concatenate()([x, s])

    merged = layers.Dense(16, activation="relu", kernel_regularizer=l2)(x)
    merged = layers.Dropout(0.4)(merged)
    output = layers.Dense(1, activation="linear", name="prediction")(merged)

    model = keras.Model(inputs=inputs, outputs=output)
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=5e-4), loss="mse", metrics=["mae"])
    return model


def model_inputs(X_seq: np.ndarray, X_static: np.ndarray) -> dict[str, np.ndarray]:
    """Keras feed dict, omitting the static branch when it doesn't exist."""
    if X_static.shape[1] == 0:
        return {"sequence_input": X_seq}
    return {"sequence_input": X_seq, "static_input": X_static}


def predict(model: keras.Model, X_seq, X_static_scaled, log_target: bool = False) -> np.ndarray:
    """Predictions in the TARGET's own units. When the model was trained on a
    log1p-compressed target, the inverse is applied here, so every caller —
    metrics, SHAP, the API — sees hoppers/hill or % damage either way and never
    has to know how the model was fitted."""
    y_pred = model.predict(model_inputs(X_seq, X_static_scaled), verbose=0).flatten()
    if log_target:
        y_pred = np.expm1(y_pred)
    return np.maximum(y_pred, 0.0)


def band_sample_weights(
    pest: str, y: np.ndarray, is_reproductive: np.ndarray, power: float = 1.0
) -> np.ndarray:
    """Inverse-frequency weight per ETL band, raised to `power`.

    Plain MSE on a right-skewed target pulls every prediction toward the mean,
    which on this data sits inside the Low band — so the model never crosses a
    High cutoff and High-band recall collapses to zero. Weighting each sample
    by the inverse frequency of its own band tells the optimizer that the rare
    High windows cost as much to miss as the common Low ones, which is also the
    agronomic reality: a missed outbreak costs more than a false alarm.

    `power` controls how hard that correction is applied:
      1.0 — full inverse frequency. Strongest pull toward the rare bands, but
            when a band has only a handful of samples (RSB's High band has 4 in
            the test split) it hands those few enormous weight and destabilizes
            the fit — measured: RSB R2 fell 0.206 -> 0.035.
      0.5 — square root of the inverse frequency. The usual middle ground:
            still corrects the imbalance, without letting a 4-sample band
            dominate the gradient.
      0.0 — no weighting, identical to leaving the flag off.
    """
    levels = np.array(to_risk_levels(pest, y, is_reproductive))
    weights = np.ones(len(levels), dtype=np.float32)
    n_levels = len(np.unique(levels))
    for level in np.unique(levels):
        mask = levels == level
        weights[mask] = (len(levels) / (n_levels * mask.sum())) ** power
    return weights


def regression_metrics(y, y_pred) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, y_pred))),
        "mae": float(mean_absolute_error(y, y_pred)),
        "r2": float(r2_score(y, y_pred)),
    }


def evaluate(
    model: keras.Model, X_seq, X_static_scaled, y, pest: str, is_reproductive, log_target: bool = False
) -> dict:
    """Both halves of RQ1.1: the regression scores for the continuous forecast,
    and the downstream agreement after the ETL mapping buckets it into
    Low/Medium/High (ml/bilstm/etl_metrics.py). Always scored in the target's
    own units, never in log space."""
    y_pred = predict(model, X_seq, X_static_scaled, log_target)
    return {
        **regression_metrics(y, y_pred),
        "etl_classification": classification_agreement(pest, y, y_pred, is_reproductive),
    }


def scale_static(X_train, X_val, X_test):
    """None when the configuration has no static vector (the raw control)."""
    if X_train.shape[1] == 0:
        return X_train, X_val, X_test, None
    scaler = StandardScaler().fit(X_train)
    return scaler.transform(X_train), scaler.transform(X_val), scaler.transform(X_test), scaler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--features",
        choices=["engineered", "raw", "lagged"],
        default="engineered",
        help="Which build_sequences.py configuration to train on. 'raw' is the RQ2 control. "
        "Anything other than 'engineered' is saved under its own suffix so it never "
        "overwrites the deployed model.",
    )
    parser.add_argument(
        "--log-target",
        action="store_true",
        help="Fit on log1p(y) and invert at prediction time. Compresses the right-skewed "
        "target so the model stops collapsing toward the Low band.",
    )
    parser.add_argument(
        "--balance-bands",
        action="store_true",
        help="Weight each training sample by the inverse frequency of its ETL band, so rare "
        "High-risk windows carry as much loss as common Low ones.",
    )
    parser.add_argument(
        "--band-weight-power",
        type=float,
        default=1.0,
        help="How hard --balance-bands corrects the imbalance: 1.0 = full inverse frequency, "
        "0.5 = square root (gentler, safer when a band has very few samples).",
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Extra suffix for the saved weights/scalers/metrics, for running an experiment "
        "without touching the deployed model (e.g. --tag logw).",
    )
    args = parser.parse_args()

    pest = args.pest
    params = PEST_PARAMS[pest]
    X_sequence, X_static, y, meta, seq_cols, static_cols = load_dataset(pest, args.features)
    splits = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)

    train_idx, val_idx, test_idx = splits["train"], splits["val"], splits["test"]
    print(f"{pest} ({args.features}): train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    X_seq_train, X_seq_val, X_seq_test, sequence_scaler = scale_sequence(
        X_sequence[train_idx], X_sequence[val_idx], X_sequence[test_idx]
    )

    X_static_train, X_static_val, X_static_test, static_scaler = scale_static(
        X_static[train_idx], X_static[val_idx], X_static[test_idx]
    )

    y_train, y_val, y_test = y[train_idx], y[val_idx], y[test_idx]
    is_reproductive = meta["is_reproductive"].to_numpy()
    is_reproductive_test = is_reproductive[test_idx]

    # Band weights are computed from the UNTRANSFORMED target, so the band a
    # sample belongs to is the same one the ETL check will score it against.
    sample_weight = (
        band_sample_weights(pest, y_train, is_reproductive[train_idx], args.band_weight_power)
        if args.balance_bands
        else None
    )

    # The transform is applied after the weights and after the split, and is
    # undone inside predict(), so everything downstream stays in real units.
    y_fit, y_fit_val = (np.log1p(y_train), np.log1p(y_val)) if args.log_target else (y_train, y_val)

    model = build_model(
        window_days=X_sequence.shape[1],
        n_seq_features=X_sequence.shape[2],
        n_static_features=X_static.shape[1],
    )
    model.summary()

    early_stopping = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=15, restore_best_weights=True
    )

    model.fit(
        model_inputs(X_seq_train, X_static_train),
        y_fit,
        sample_weight=sample_weight,
        validation_data=(model_inputs(X_seq_val, X_static_val), y_fit_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=[early_stopping],
        verbose=2,
    )

    test_metrics = evaluate(
        model, X_seq_test, X_static_test, y_test, pest, is_reproductive_test, args.log_target
    )
    test_metrics["feature_set"] = args.features
    test_metrics["log_target"] = args.log_target
    test_metrics["balance_bands"] = args.balance_bands
    if args.balance_bands:
        test_metrics["band_weight_power"] = args.band_weight_power
    print(f"{pest} test metrics (regression + ETL agreement):", json.dumps(test_metrics, indent=2))

    suffix = FEATURE_SET_SUFFIX[args.features] + (f"_{args.tag}" if args.tag else "")
    weights_path = params.bilstm_weights_path
    if suffix:
        weights_path = weights_path.with_name(f"{weights_path.stem}{suffix}{weights_path.suffix}")
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(weights_path)

    scalers_path = weights_path.parent / f"bilstm_{pest.lower()}{suffix}_scalers.joblib"
    joblib.dump(
        {
            "sequence_scaler": sequence_scaler,
            "static_scaler": static_scaler,
            "sequence_feature_columns": seq_cols,
            "static_feature_columns": static_cols,
            # Read back by app/models/bilstm_model.py so a log-trained model
            # promoted to deployment still serves hoppers/hill and % damage
            # rather than log-space numbers. Without this, promoting a
            # --log-target run would silently under-report every forecast and
            # push every ETL band down.
            "log_target": args.log_target,
        },
        scalers_path,
    )

    metrics_path = weights_path.parent / f"bilstm_{pest.lower()}{suffix}_test_metrics.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))

    print(f"Saved model to {weights_path}")
    print(f"Saved scalers to {scalers_path} (required at inference time — app/models/bilstm_model.py must load these before calling predict())")
    print(f"Saved test metrics to {metrics_path}")


if __name__ == "__main__":
    main()

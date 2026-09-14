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

from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS, SEQUENCES_DIR

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
# TEST_FRACTION is whatever remains (~0.15)


def load_dataset(pest: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame, list[str], list[str]]:
    npz_path = SEQUENCES_DIR / f"{pest.lower()}_sequences.npz"
    data = np.load(npz_path, allow_pickle=True)
    meta = pd.read_csv(SEQUENCES_DIR / f"{pest.lower()}_sequences_meta.csv", parse_dates=["target_date"])
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
    """
    l2 = keras.regularizers.l2(1e-3)

    sequence_input = keras.Input(shape=(window_days, n_seq_features), name="sequence_input")
    static_input = keras.Input(shape=(n_static_features,), name="static_input")

    x = layers.Bidirectional(layers.LSTM(16, kernel_regularizer=l2, recurrent_dropout=0.1))(sequence_input)
    x = layers.Dropout(0.4)(x)

    s = layers.Dense(8, activation="relu", kernel_regularizer=l2)(static_input)

    merged = layers.Concatenate()([x, s])
    merged = layers.Dense(16, activation="relu", kernel_regularizer=l2)(merged)
    merged = layers.Dropout(0.4)(merged)
    output = layers.Dense(1, activation="linear", name="prediction")(merged)

    model = keras.Model(inputs=[sequence_input, static_input], outputs=output)
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=5e-4), loss="mse", metrics=["mae"])
    return model


def evaluate(model: keras.Model, X_seq, X_static_scaled, y) -> dict[str, float]:
    y_pred = model.predict({"sequence_input": X_seq, "static_input": X_static_scaled}, verbose=0).flatten()
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, y_pred))),
        "mae": float(mean_absolute_error(y, y_pred)),
        "r2": float(r2_score(y, y_pred)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    pest = args.pest
    params = PEST_PARAMS[pest]

    X_sequence, X_static, y, meta, seq_cols, static_cols = load_dataset(pest)
    splits = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)

    train_idx, val_idx, test_idx = splits["train"], splits["val"], splits["test"]
    print(f"{pest}: train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    X_seq_train, X_seq_val, X_seq_test, sequence_scaler = scale_sequence(
        X_sequence[train_idx], X_sequence[val_idx], X_sequence[test_idx]
    )

    static_scaler = StandardScaler().fit(X_static[train_idx])
    X_static_train = static_scaler.transform(X_static[train_idx])
    X_static_val = static_scaler.transform(X_static[val_idx])
    X_static_test = static_scaler.transform(X_static[test_idx])

    y_train, y_val, y_test = y[train_idx], y[val_idx], y[test_idx]

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
        {"sequence_input": X_seq_train, "static_input": X_static_train},
        y_train,
        validation_data=({"sequence_input": X_seq_val, "static_input": X_static_val}, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=[early_stopping],
        verbose=2,
    )

    test_metrics = evaluate(model, X_seq_test, X_static_test, y_test)
    print(f"{pest} test metrics (regression, per panel fix #1):", json.dumps(test_metrics, indent=2))

    weights_path = params.bilstm_weights_path
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(weights_path)

    scalers_path = weights_path.parent / f"bilstm_{pest.lower()}_scalers.joblib"
    joblib.dump(
        {
            "sequence_scaler": sequence_scaler,
            "static_scaler": static_scaler,
            "sequence_feature_columns": seq_cols,
            "static_feature_columns": static_cols,
        },
        scalers_path,
    )

    metrics_path = weights_path.parent / f"bilstm_{pest.lower()}_test_metrics.json"
    metrics_path.write_text(json.dumps(test_metrics, indent=2))

    print(f"Saved model to {weights_path}")
    print(f"Saved scalers to {scalers_path} (required at inference time — app/models/bilstm_model.py must load these before calling predict())")
    print(f"Saved test metrics to {metrics_path}")


if __name__ == "__main__":
    main()

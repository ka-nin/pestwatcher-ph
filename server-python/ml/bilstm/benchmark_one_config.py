"""Trains ONE (pest, feature_set) configuration once, chronologically split
exactly like ml/bilstm/train.py, and prints a single JSON line with wall-clock
training time, per-sample inference latency, and regression metrics.

Deliberately a separate, single-shot process (not a loop over configs in one
Python session) so each run gets its own process for `/usr/bin/time -l` to
measure peak memory footprint cleanly — a shared session's memory would be
dirtied by whichever config ran first, which is why
ml/bilstm/benchmark_efficiency.py (the driver) shells out to this file once
per configuration instead of importing it.

This answers the panel's "baseline BiLSTM vs proposed framework" ask
directly: engineered = the deployed configuration, raw = the thesis's
existing RQ2/RQ3 control (Tmax/Tmin/RH/rainfall only, no static vector) —
the same "baseline" the panel means. seq_only is also supported, for anyone
who wants the narrower ablation's efficiency numbers too, but engineered vs
raw is the comparison that maps onto what was actually asked for.

Run from server-python/ (not meant to be run directly under /usr/bin/time by
a human — see benchmark_efficiency.py, which does that for you):
    .venv/bin/python -m ml.bilstm.benchmark_one_config --pest BPH --features engineered
"""

import argparse
import json
import time

import numpy as np

from ml.bilstm.train import (
    build_model,
    chronological_split,
    load_dataset,
    model_inputs,
    predict,
    regression_metrics,
    scale_sequence,
    scale_static,
)
from tensorflow import keras

from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

EPOCHS = 60
BATCH_SIZE = 32
# How many individual (non-batched) predict() calls to time for the
# inference-latency figure — one at a time, the way a live forecast request
# actually calls it (app/routers/inference.py's _run_forecast: one window,
# one prediction), not a batched throughput number.
N_LATENCY_SAMPLES = 100


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--features", choices=["engineered", "raw", "seq_only", "lagged", "lagged_fresh"], required=True)
    args = parser.parse_args()

    X_seq, X_static, y, meta, _, _ = load_dataset(args.pest, args.features)
    window_days = PEST_PARAMS[args.pest].crf_window_days
    splits = chronological_split(meta, window_days, FORECAST_HORIZON_DAYS)
    train_idx, val_idx, test_idx = splits["train"], splits["val"], splits["test"]

    X_seq_fit, X_seq_val, X_seq_test, _ = scale_sequence(X_seq[train_idx], X_seq[val_idx], X_seq[test_idx])
    X_static_fit, X_static_val, X_static_test, _ = scale_static(
        X_static[train_idx], X_static[val_idx], X_static[test_idx]
    )

    keras.backend.clear_session()
    model = build_model(
        window_days=X_seq.shape[1], n_seq_features=X_seq.shape[2], n_static_features=X_static.shape[1]
    )

    train_start = time.perf_counter()
    history = model.fit(
        model_inputs(X_seq_fit, X_static_fit),
        y[train_idx],
        validation_data=(model_inputs(X_seq_val, X_static_val), y[val_idx]),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)],
        verbose=0,
    )
    train_seconds = time.perf_counter() - train_start
    epochs_run = len(history.history["loss"])

    y_pred = predict(model, X_seq_test, X_static_test)
    metrics = regression_metrics(y[test_idx], y_pred)

    # One-at-a-time inference latency, matching how a live request actually
    # calls predict() — a single window in, a single value out, not a batch.
    n_latency = min(N_LATENCY_SAMPLES, len(test_idx))
    latencies_ms = []
    for i in range(n_latency):
        single_seq = X_seq_test[i : i + 1]
        single_static = X_static_test[i : i + 1]
        t0 = time.perf_counter()
        predict(model, single_seq, single_static)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    result = {
        "pest": args.pest,
        "features": args.features,
        "n_train": int(len(train_idx)),
        "n_test": int(len(test_idx)),
        "n_seq_features": int(X_seq.shape[2]),
        "n_static_features": int(X_static.shape[1]),
        "epochs_run": epochs_run,
        "epochs_cap": EPOCHS,
        "train_seconds": train_seconds,
        "train_seconds_per_epoch": train_seconds / epochs_run if epochs_run else None,
        "inference_latency_ms_mean": float(np.mean(latencies_ms)),
        "inference_latency_ms_p95": float(np.percentile(latencies_ms, 95)),
        "n_latency_samples": n_latency,
        **metrics,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

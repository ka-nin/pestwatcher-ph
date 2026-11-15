"""EXPERIMENT ONLY: did the trained BiLSTM learn the biological quantities by itself?

The live model is given raw daily weather and the growth stage, and no formula is
calculated for it. This script asks whether what it learned INSIDE the network carries the
quantities the formulas would give: growing degree days (GDD), cumulative rainfall (CRF),
humidity persistence (HP), water stress (WSI), the rainfall and temperature trends, mean
vapor pressure deficit and mean diurnal range.

Method (a "probe"):
  1. Run the trained model on windows it was never fitted on (the chronological test
     split) and keep the values of its BiLSTM layer (32 numbers per window).
  2. Calculate each formula for the same windows, OFFLINE, as an answer key only. The
     formulas are never inputs to the model.
  3. Fit a plain linear (ridge) regression from the BiLSTM values to each answer, on the
     training windows, and score it with R-squared on the TEST windows.

Two controls say what the score means:
  - UNTRAINED: the same network with random weights, same probe. A random recurrent network
    can already carry some sums, so the trained model has to beat it to show learning.
  - RAW MEANS: a probe on just the average of each raw reading over the window, with no
    network at all. Formulas such as GDD are not simple averages, so the trained network
    has to beat this to show it learned something non-trivial.

Run from server-python/:
    PYTHONPATH=. .venv/bin/python -m ml.ablation.probe_learned_features --pest BPH
Output: ml/weights/{pest}/bilstm_{pest}_learned_feature_probe.json
"""

import argparse
import json

import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.metrics import r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow import keras

from ml.ablation.hand_features import (
    calculate_crf,
    calculate_diurnal_range,
    calculate_gdd,
    calculate_hp,
    calculate_trend,
    calculate_vpd,
    calculate_wsi,
)
from ml.bilstm.train import build_model, chronological_split, load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

NAMES = {
    "gdd": "Growing degree days (accumulated heat)",
    "crf": "Cumulative rainfall",
    "hp": "Humidity persistence",
    "wsi": "Water stress index",
    "rainfall_trend": "Rainfall trend",
    "temp_trend": "Temperature trend",
    "vpd": "Mean vapor pressure deficit",
    "diurnal": "Mean diurnal temperature range",
}


def answer_key(X_raw: np.ndarray, pest: str) -> dict[str, np.ndarray]:
    """The formulas, computed offline on raw windows (n, days, >=4: Tmax, Tmin, RH, rain)."""
    params = PEST_PARAMS[pest]
    out = {k: [] for k in NAMES}
    for w in X_raw:
        tmax, tmin, rh, rain = (w[:, i].tolist() for i in range(4))
        out["gdd"].append(calculate_gdd(tmax, tmin, base_temp_c=params.gdd_base_temp_c))
        out["crf"].append(calculate_crf(rain))
        out["hp"].append(calculate_hp(rh, rh_threshold=params.hp_rh_threshold_pct))
        out["wsi"].append(calculate_wsi(rain))
        out["rainfall_trend"].append(calculate_trend(rain))
        out["temp_trend"].append(calculate_trend([(a + b) / 2 for a, b in zip(tmax, tmin)]))
        out["vpd"].append(calculate_vpd(tmax, tmin, rh))
        out["diurnal"].append(calculate_diurnal_range(tmax, tmin))
    return {k: np.array(v) for k, v in out.items()}


def hidden_values(model: keras.Model, X_seq_scaled: np.ndarray) -> np.ndarray:
    layer = next(l for l in model.layers if isinstance(l, keras.layers.Bidirectional))
    probe = keras.Model(inputs=model.inputs[0], outputs=layer.output)
    return probe.predict(X_seq_scaled, verbose=0, batch_size=512)


def probe_r2(H_train, H_test, y_train, y_test) -> float:
    scaler = StandardScaler().fit(H_train)
    ridge = RidgeCV(alphas=np.logspace(-3, 3, 13)).fit(scaler.transform(H_train), y_train)
    return float(r2_score(y_test, ridge.predict(scaler.transform(H_test))))


def run(pest: str, seed: int = 0) -> dict:
    import joblib

    params = PEST_PARAMS[pest]
    X_seq, _, _, meta, _, _ = load_dataset(pest, "plain_fresh")
    splits = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)
    train_idx, test_idx = splits["train"], splits["test"]

    scalers = joblib.load(params.bilstm_weights_path.parent / f"bilstm_{pest.lower()}_scalers.joblib")
    n, w, f = X_seq.shape
    X_scaled = scalers["sequence_scaler"].transform(X_seq.reshape(-1, f)).reshape(n, w, f)

    keras.utils.set_random_seed(seed)
    trained = keras.models.load_model(params.bilstm_weights_path)
    untrained = build_model(w, f, 3)

    H_trained = hidden_values(trained, X_scaled)
    H_untrained = hidden_values(untrained, X_scaled)
    raw_means = np.concatenate([X_seq[:, :, :4].mean(axis=1), X_seq[:, :, 4:].mean(axis=1)], axis=1)

    key = answer_key(X_seq[:, :, :4], pest)
    rows = {}
    for name, label in NAMES.items():
        y = key[name]
        rows[name] = {
            "label": label,
            "trained_bilstm": probe_r2(H_trained[train_idx], H_trained[test_idx], y[train_idx], y[test_idx]),
            "untrained_bilstm": probe_r2(H_untrained[train_idx], H_untrained[test_idx], y[train_idx], y[test_idx]),
            "raw_means_only": probe_r2(raw_means[train_idx], raw_means[test_idx], y[train_idx], y[test_idx]),
        }
    return {
        "pest": pest,
        "windows_train": int(len(train_idx)),
        "windows_test": int(len(test_idx)),
        "hidden_values_per_window": int(H_trained.shape[1]),
        "scores_are": "R-squared of a linear probe on windows the model never saw (chronological test split)",
        "results": rows,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = ap.parse_args()
    result = run(args.pest)
    out = PEST_PARAMS[args.pest].bilstm_weights_path.parent / f"bilstm_{args.pest.lower()}_learned_feature_probe.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"{args.pest}: {result['windows_train']} train / {result['windows_test']} test windows")
    print(f"{'feature':38}{'trained':>9}{'untrained':>11}{'raw means':>11}")
    for r in result["results"].values():
        print(f"{r['label']:38}{r['trained_bilstm']:9.2f}{r['untrained_bilstm']:11.2f}{r['raw_means_only']:11.2f}")
    print("saved", out)

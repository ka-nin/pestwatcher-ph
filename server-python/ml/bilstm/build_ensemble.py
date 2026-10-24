"""Turns five trained runs of the deployed model into a forecast with a confidence band.

The five runs (the deployed bilstm_{pest}.keras plus bilstm_{pest}_plain_fresh_e2..e5) see the
same data and differ only in their random start. Averaging them barely changes accuracy, but how
much they DISAGREE tracks how wrong the forecast turns out to be, so it is used to size a band.

The band is split-conformal, calibrated on the VALIDATION windows (never the test windows):
  score  = |actual - mean forecast| / (disagreement + floor)
  width  = the 80th percentile of that score
  band   = mean forecast +/- width * (disagreement + floor)
so the band is wider where the runs disagree, and is sized so that about 80% of validation
forecasts fall inside. Coverage on the unseen test windows is measured and saved alongside.

Run from server-python/:
    PYTHONPATH=. .venv/bin/python -m ml.bilstm.build_ensemble --pest BPH
Output: ml/weights/{pest}/bilstm_{pest}_ensemble.json (members, width, floor, coverage)
"""

import argparse
import json

import joblib
import numpy as np
from tensorflow import keras

from ml.bilstm.train import chronological_split, load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

TARGET_COVERAGE = 0.80
MEMBER_TAGS = ["", "e2", "e3", "e4", "e5"]  # "" = the deployed model itself


def member_paths(pest: str):
    d = PEST_PARAMS[pest].bilstm_weights_path.parent
    for tag in MEMBER_TAGS:
        if tag == "":
            yield d / f"bilstm_{pest.lower()}.keras", d / f"bilstm_{pest.lower()}_scalers.joblib"
        else:
            yield d / f"bilstm_{pest.lower()}_plain_fresh_{tag}.keras", d / f"bilstm_{pest.lower()}_plain_fresh_{tag}_scalers.joblib"


def predict_members(pest: str, X_seq: np.ndarray, X_static: np.ndarray) -> np.ndarray:
    out = []
    for model_path, scaler_path in member_paths(pest):
        sc = joblib.load(scaler_path)
        n, w, f = X_seq.shape
        a = sc["sequence_scaler"].transform(X_seq.reshape(-1, f)).reshape(n, w, f)
        b = sc["static_scaler"].transform(X_static)
        m = keras.models.load_model(model_path)
        out.append(np.maximum(m.predict({"sequence_input": a, "static_input": b}, verbose=0).flatten(), 0.0))
    return np.array(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    pest = ap.parse_args().pest
    params = PEST_PARAMS[pest]

    X_seq, X_static, y, meta, _, _ = load_dataset(pest, "plain_fresh")
    splits = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)
    val, test = splits["val"], splits["test"]

    pv = predict_members(pest, X_seq[val], X_static[val])
    pt = predict_members(pest, X_seq[test], X_static[test])
    mean_v, sd_v = pv.mean(0), pv.std(0)
    mean_t, sd_t = pt.mean(0), pt.std(0)

    floor = float(0.1 * sd_v.mean())  # keeps the band from collapsing where runs happen to agree
    width = float(np.quantile(np.abs(y[val] - mean_v) / (sd_v + floor), TARGET_COVERAGE))

    def covered(y_true, mean, sd):
        return float(np.mean(np.abs(y_true - mean) <= width * (sd + floor)))

    result = {
        "pest": pest,
        "members": len(MEMBER_TAGS),
        "target_coverage": TARGET_COVERAGE,
        "band_width_factor": width,
        "disagreement_floor": floor,
        "coverage_on_validation": covered(y[val], mean_v, sd_v),
        "coverage_on_test": covered(y[test], mean_t, sd_t),
        "mean_band_half_width_test": float(np.mean(width * (sd_t + floor))),
        "test_rmse_single_deployed": float(np.sqrt(np.mean((pt[0] - y[test]) ** 2))),
        "test_rmse_ensemble_mean": float(np.sqrt(np.mean((mean_t - y[test]) ** 2))),
    }
    out = params.bilstm_weights_path.parent / f"bilstm_{pest.lower()}_ensemble.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

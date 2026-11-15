"""Does a verified report actually improve the forecast, and by how much
depending on its age? Scores lagged-input BiLSTM variants on the same
held-out test windows (ml/bilstm/train.py's chronological split) under
controlled conditions:

  no report          the "no report on file" encoding, the usual live case
  report, age N days the true stage-matched pest value N days before the
                     window ends, as a technologist-verified report would
                     carry it

The engineered (weather + growth stage, no report input) model is scored
alongside as the reference a report-taking model has to beat.

A model where the report "works" should match the reference with no report,
and beat it by more the fresher the report is. The deployed model was trained
on a simulated cadence that gave ~98% of windows a ~9-day-old report, so it
barely learned either case; `lagged_fresh` (build_sequences.py) is the retrain
meant to fix that.

Run from server-python/:
    .venv/bin/python -m ml.bilstm.evaluate_observation_response

Output: ml/weights/bilstm_observation_response.json
"""

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from tensorflow import keras

from ml.bilstm.build_sequences import MAX_OBSERVATION_AGE_DAYS, load_clean_daily, target_value
from ml.bilstm.train import chronological_split, load_dataset, predict
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS, WEIGHTS_DIR

AGES = [0, 7, 14, 30]
CANDIDATES = {
    "deployed (lagged, simulated cadence)": "bilstm_{p}_lagged",
    "lagged + 50% observation dropout": "bilstm_{p}_lagged_obsdrop",
    "lagged_fresh (retrained)": "bilstm_{p}_lagged_fresh",
}
OUT_PATH = WEIGHTS_DIR / "bilstm_observation_response.json"


def observations_at_age(pest: str, age: int) -> np.ndarray:
    """(n_windows, 3) report triples at a fixed age, in the same row order
    build_sequences.py writes (municipality, then window start)."""
    df = load_clean_daily()
    window_days = PEST_PARAMS[pest].crf_window_days
    rows = []
    for _, group in df.groupby("Municipality"):
        group = group.reset_index(drop=True)
        last_start = len(group) - window_days - FORECAST_HORIZON_DAYS
        bucket = group["growth_stage_bucket"].to_numpy()
        for start in range(0, last_start + 1):
            end = start + window_days - 1
            idx = end - age
            is_reproductive = 1.0 if bucket[end] == "Reproductive" else 0.0
            if idx < 0:
                rows.append([0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0])
            else:
                rows.append([target_value(group.iloc[idx], pest, is_reproductive), float(age), 1.0])
    return np.asarray(rows, dtype=np.float32)


def score(y, y_pred) -> dict:
    return {"r2": float(r2_score(y, y_pred)), "mae": float(mean_absolute_error(y, y_pred))}


def main() -> None:
    results = {}
    for pest in PEST_PARAMS:
        p = pest.lower()
        X_seq, X_static9, y, meta, _, _ = load_dataset(pest, "engineered")
        test = chronological_split(meta, PEST_PARAMS[pest].crf_window_days, FORECAST_HORIZON_DAYS)["test"]
        y_test = y[test]

        conditions = {"no report": np.tile([0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0], (len(test), 1))}
        for age in AGES:
            conditions[f"report, age {age}d"] = observations_at_age(pest, age)[test]

        pest_out = {}
        reference = json.loads((WEIGHTS_DIR / p / f"bilstm_{p}_weatheronly_test_metrics.json").read_text())
        pest_out["reference: engineered, no report input"] = {"any": {"r2": reference["r2"], "mae": reference["mae"]}}

        for label, stem in CANDIDATES.items():
            stem = stem.format(p=p)
            model_path = WEIGHTS_DIR / p / f"{stem}.keras"
            if not model_path.exists():
                continue
            model = keras.models.load_model(model_path)
            scalers = joblib.load(WEIGHTS_DIR / p / f"{stem}_scalers.joblib")
            n, w, f = X_seq[test].shape
            seq = scalers["sequence_scaler"].transform(X_seq[test].reshape(-1, f)).reshape(n, w, f)
            per_condition = {}
            for cond, obs in conditions.items():
                static = scalers["static_scaler"].transform(np.hstack([X_static9[test], obs]))
                per_condition[cond] = score(y_test, predict(model, seq, static, bool(scalers.get("log_target"))))
            pest_out[label] = per_condition
        results[pest] = pest_out

        print(f"\n=== {pest}: test R² by condition ===")
        print(f"  {'reference: engineered, no report input':40} {reference['r2']:.3f}")
        header = "  " + " " * 40 + "".join(f"{c:>17}" for c in conditions)
        print(header)
        for label, per in pest_out.items():
            if label.startswith("reference"):
                continue
            print(f"  {label:40}" + "".join(f"{per[c]['r2']:17.3f}" for c in conditions))

    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()

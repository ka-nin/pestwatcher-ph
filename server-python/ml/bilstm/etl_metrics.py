"""Downstream IPM classification agreement for the BiLSTM's continuous forecast.

This is the second half of the thesis's RQ1.1 (and RQ2.2): the model itself is
scored as a regressor (RMSE/MAE/R2, see ml/bilstm/train.py), then its continuous
output is mapped through the fixed ETL table (app/decision/etl_thresholds.py)
into Low/Medium/High and scored AGAIN as a classifier against the same mapping
applied to the observed value.

Nothing here is learned. Both sides of the comparison use the identical
`derive_risk_level` call the live API uses, so "classification agreement" means
exactly what the paper says it means: how often the forecast lands in the same
IPM decision band as the ground truth, not how well a separate classifier head
was trained.

Which ETL band applies depends on the growth-stage bucket, which varies per
sample. That comes from the sequence metadata's `is_reproductive` column
(written by ml/bilstm/build_sequences.py) rather than from the static feature
vector, so the raw-feature baseline — which has no static vector at all — is
bucketed exactly the same way as the engineered configuration.

Precision/recall/F1 are MACRO-averaged over the three bands. The paper states
them in their binary form; with three classes, macro is the unweighted mean of
the per-band score, which keeps a rare High band from being drowned out by a
common Low band. Report it as macro in the defense.

Run as a script to score the ALREADY-TRAINED model for both pests and merge the
result into its existing bilstm_{pest}_test_metrics.json, without retraining
and without touching the saved weights or the regression numbers already cited:

    .venv/Scripts/python.exe -m ml.bilstm.etl_metrics
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from app.decision.etl_thresholds import derive_risk_level

RISK_LEVELS = ["Low", "Medium", "High"]


def to_risk_levels(pest: str, values: np.ndarray, is_reproductive: np.ndarray) -> list[str]:
    """Maps continuous forecasts (or observed values) to Low/Medium/High using
    the per-sample growth-stage bucket."""
    return [
        derive_risk_level(pest, "Reproductive" if repro else "Vegetative", float(value))
        for value, repro in zip(values, is_reproductive)
    ]


def classification_agreement(
    pest: str, y_true: np.ndarray, y_pred: np.ndarray, is_reproductive: np.ndarray
) -> dict:
    """Accuracy/Precision/Recall/F1 + confusion matrix for the ETL-derived
    risk levels. Keys match the thesis's Table 3 metric names."""
    true_levels = to_risk_levels(pest, y_true, is_reproductive)
    pred_levels = to_risk_levels(pest, y_pred, is_reproductive)

    return {
        "accuracy": float(accuracy_score(true_levels, pred_levels)),
        "precision_macro": float(
            precision_score(true_levels, pred_levels, labels=RISK_LEVELS, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            recall_score(true_levels, pred_levels, labels=RISK_LEVELS, average="macro", zero_division=0)
        ),
        "f1_macro": float(
            f1_score(true_levels, pred_levels, labels=RISK_LEVELS, average="macro", zero_division=0)
        ),
        "confusion_matrix": confusion_matrix(true_levels, pred_levels, labels=RISK_LEVELS).tolist(),
        "confusion_matrix_labels": RISK_LEVELS,
        "support_per_level": {
            level: int(sum(1 for t in true_levels if t == level)) for level in RISK_LEVELS
        },
    }


def score_saved_model(pest: str) -> dict | None:
    """Re-scores the model already on disk against the same held-out test split
    ml/bilstm/train.py used, and returns its ETL agreement. Nothing is
    retrained: the saved weights and the saved scalers are loaded as-is, so the
    regression metrics in the file stay exactly as they were reported."""
    from tensorflow import keras

    from ml.bilstm.train import chronological_split, load_dataset, model_inputs
    from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

    params = PEST_PARAMS[pest]
    scalers_path = params.bilstm_weights_path.parent / f"bilstm_{pest.lower()}_scalers.joblib"
    if not params.bilstm_weights_path.exists() or not scalers_path.exists():
        print(f"{pest}: no trained model/scalers on disk — skipping.")
        return None

    X_sequence, X_static, y, meta, _, _ = load_dataset(pest, "engineered")
    if "is_reproductive" not in meta.columns:
        print(f"{pest}: sequence metadata predates the is_reproductive column — rerun build_sequences.")
        return None

    splits = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)
    test_idx = splits["test"]

    scalers = joblib.load(scalers_path)
    n_features = X_sequence.shape[2]
    X_seq_test = scalers["sequence_scaler"].transform(
        X_sequence[test_idx].reshape(-1, n_features)
    ).reshape(len(test_idx), X_sequence.shape[1], n_features)
    X_static_test = scalers["static_scaler"].transform(X_static[test_idx])

    model = keras.models.load_model(params.bilstm_weights_path)
    y_pred = model.predict(model_inputs(X_seq_test, X_static_test), verbose=0).flatten()

    return classification_agreement(
        pest, y[test_idx], y_pred, meta["is_reproductive"].to_numpy()[test_idx]
    )


def main() -> None:
    from ml.config import PEST_PARAMS

    for pest in PEST_PARAMS:
        result = score_saved_model(pest)
        if result is None:
            continue

        metrics_path = (
            PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_test_metrics.json"
        )
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            metrics = {}

        metrics["etl_classification"] = result
        metrics_path.write_text(json.dumps(metrics, indent=2))

        print(f"\n=== {pest} — downstream IPM classification agreement (RQ1.1.2) ===")
        print(
            f"accuracy={result['accuracy']:.4f}  precision={result['precision_macro']:.4f}  "
            f"recall={result['recall_macro']:.4f}  f1={result['f1_macro']:.4f}  (macro)"
        )
        print("support per band:", result["support_per_level"])
        print(
            pd.DataFrame(
                result["confusion_matrix"],
                index=[f"actual {level}" for level in RISK_LEVELS],
                columns=[f"pred {level}" for level in RISK_LEVELS],
            ).to_string()
        )
        print(f"Merged into {metrics_path}")


if __name__ == "__main__":
    main()

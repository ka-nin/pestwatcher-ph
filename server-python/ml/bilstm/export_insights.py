"""Exports the artifacts behind admin-web's Model Insights page for one pest:

  ml/weights/{pest}/bilstm_{pest}_test_predictions.json
      per-sample predicted vs actual values on the held-out test set (the
      same chronological split ml/bilstm/train.py evaluates), for the
      predicted-vs-actual scatter and the time-series chart;
  ml/weights/{pest}/bilstm_{pest}_shap_summary.json
      mean absolute SHAP influence of each input over a sample of the test
      set, so the chart shows what the model relies on overall rather than
      for one live forecast.

Nothing is retrained: it loads the DEPLOYED model and re-evaluates it on the
held-out test split, then rewrites bilstm_{pest}_test_metrics.json (RMSE/MAE/
R² + ETL agreement) alongside the predictions and SHAP, so all three always
describe the same model. Which feature set the deployed model uses
(engineered = 9 static features, lagged = 12) is read from its own saved
scaler, the same self-describing check app/models/bilstm_model.py and
ml/explainability/shap_report.py use. Before this, the script assumed the
9-feature engineered set and crashed against a lagged deployment, which is
how the metrics and SHAP files fell behind the model on 2026-10-20.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.export_insights --pest BPH
    .venv/Scripts/python.exe -m ml.bilstm.export_insights --pest RSB
"""

import argparse
import json

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.models.bilstm_model import bilstm_forecaster
from ml.bilstm.build_sequences import STATIC_FEATURE_COLUMNS
from ml.bilstm.etl_metrics import classification_agreement
from ml.bilstm.train import chronological_split, load_dataset, predict
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS
from ml.explainability.shap_report import _display_name, _get_explainer

SHAP_SAMPLE_SIZE = 60
TOP_FEATURES = 30  # effectively "all" -- 21 columns engineered, 24 lagged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = parser.parse_args()
    pest = args.pest
    params = PEST_PARAMS[pest]

    bilstm_forecaster.load(pest)
    scalers = bilstm_forecaster.scalers_for(pest)
    seq_cols = list(scalers["sequence_feature_columns"])
    static_cols = list(scalers["static_feature_columns"])
    feature_set = scalers.get("feature_set") or (
        "lagged" if len(static_cols) == len(STATIC_FEATURE_COLUMNS) + 3 else "engineered"
    )
    log_target = bool(scalers.get("log_target", False))

    X_sequence, X_static, y, meta, _, _ = load_dataset(pest, feature_set)
    test_idx = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)["test"]

    n, w, f = X_sequence[test_idx].shape
    X_seq_test = scalers["sequence_scaler"].transform(X_sequence[test_idx].reshape(-1, f)).reshape(n, w, f)
    X_static_test = scalers["static_scaler"].transform(X_static[test_idx])
    y_test = y[test_idx]

    model = bilstm_forecaster.model_for(pest)
    y_pred = predict(model, X_seq_test, X_static_test, log_target)

    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))
    is_reproductive_test = meta["is_reproductive"].to_numpy()[test_idx]

    out_dir = params.bilstm_weights_path.parent
    test_metrics = {
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "etl_classification": classification_agreement(pest, y_test, y_pred, is_reproductive_test),
        "feature_set": feature_set,
        "log_target": log_target,
    }
    (out_dir / f"bilstm_{pest.lower()}_test_metrics.json").write_text(json.dumps(test_metrics, indent=2))
    print(f"{pest}: deployed feature set = {feature_set}, n_test={len(test_idx)}")
    print(f"  rmse={rmse:.4f} mae={mae:.4f} r2={r2:.4f}  etl_accuracy={test_metrics['etl_classification']['accuracy']:.4f}")

    rows = meta.loc[test_idx]
    predictions = {
        "n": int(len(test_idx)),
        "metrics_recomputed": {"rmse": rmse, "mae": mae, "r2": r2},
        "points": [
            {
                "date": row.target_date.strftime("%Y-%m-%d"),
                "municipality": row.municipality,
                "actual": round(float(actual), 4),
                "predicted": round(float(predicted), 4),
            }
            for row, actual, predicted in zip(rows.itertuples(index=False), y_test, y_pred)
        ],
    }
    (out_dir / f"bilstm_{pest.lower()}_test_predictions.json").write_text(json.dumps(predictions))

    # ---- global SHAP: mean |SHAP| per input over an evenly spaced test sample
    explainer = _get_explainer(pest)
    sample = np.linspace(0, len(test_idx) - 1, min(SHAP_SAMPLE_SIZE, len(test_idx))).astype(int)
    shap_seq, shap_static = explainer.shap_values([X_seq_test[sample], X_static_test[sample]])
    shap_seq = np.squeeze(shap_seq, axis=-1)  # (samples, window, n_seq_features)
    shap_static = np.squeeze(shap_static, axis=-1)  # (samples, n_static_features)

    # a daily feature's influence is the sum of its |SHAP| over the 14 days
    seq_importance = np.abs(shap_seq).sum(axis=1).mean(axis=0)
    static_importance = np.abs(shap_static).mean(axis=0)

    # Labels come from the scaler's own recorded column order, not a
    # hardcoded list, so a lagged model's 3 extra static inputs are named
    # rather than silently dropped by zip() against a 9-item list.
    features = [
        {"label": _display_name(c), "value": float(v), "group": "sequence"}
        for c, v in zip(seq_cols, seq_importance)
    ] + [
        {"label": _display_name(c), "value": float(v), "group": "static"}
        for c, v in zip(static_cols, static_importance)
    ]
    total = sum(item["value"] for item in features) or 1.0
    for item in features:
        item["share"] = item["value"] / total
    features.sort(key=lambda item: item["value"], reverse=True)

    (out_dir / f"bilstm_{pest.lower()}_shap_summary.json").write_text(
        json.dumps({"sample_size": int(len(sample)), "features": features[:TOP_FEATURES]}, indent=2)
    )
    print(f"  top features: {[(f['label'], round(f['share'], 3)) for f in features[:TOP_FEATURES]]}")


if __name__ == "__main__":
    main()

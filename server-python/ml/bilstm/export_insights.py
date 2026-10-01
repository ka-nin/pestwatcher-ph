"""Exports the artifacts behind admin-web's Model Insights page for one pest:

  ml/weights/{pest}/bilstm_{pest}_test_predictions.json
      per-sample predicted vs actual values on the held-out test set (the
      same chronological split ml/bilstm/train.py evaluates), for the
      predicted-vs-actual scatter and the time-series chart;
  ml/weights/{pest}/bilstm_{pest}_shap_summary.json
      mean absolute SHAP influence of each input over a sample of the test
      set, so the chart shows what the model relies on overall rather than
      for one live forecast.

Nothing is retrained: it loads the trained model, recomputes RMSE/MAE/R² and
checks them against the saved bilstm_{pest}_test_metrics.json as a sanity
check that the exported predictions really are the evaluated ones.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.export_insights --pest BPH
    .venv/Scripts/python.exe -m ml.bilstm.export_insights --pest RSB
"""

import argparse
import json

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.models.bilstm_model import bilstm_forecaster
from ml.bilstm.build_sequences import SEQUENCE_FEATURE_COLUMNS, STATIC_FEATURE_COLUMNS
from ml.bilstm.train import chronological_split, load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS
from ml.explainability.shap_report import _display_name, _get_explainer

SHAP_SAMPLE_SIZE = 60
TOP_FEATURES = 8


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = parser.parse_args()
    pest = args.pest
    params = PEST_PARAMS[pest]

    bilstm_forecaster.load(pest)
    X_sequence, X_static, y, meta, _, _ = load_dataset(pest)
    test_idx = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)["test"]

    scalers = bilstm_forecaster.scalers_for(pest)
    n, w, f = X_sequence[test_idx].shape
    X_seq_test = scalers["sequence_scaler"].transform(X_sequence[test_idx].reshape(-1, f)).reshape(n, w, f)
    X_static_test = scalers["static_scaler"].transform(X_static[test_idx])
    y_test = y[test_idx]

    model = bilstm_forecaster.model_for(pest)
    y_pred = model.predict({"sequence_input": X_seq_test, "static_input": X_static_test}, verbose=0).flatten()

    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    out_dir = params.bilstm_weights_path.parent
    saved = json.loads((out_dir / f"bilstm_{pest.lower()}_test_metrics.json").read_text())
    print(f"{pest}: n_test={len(test_idx)}")
    print(f"  recomputed  rmse={rmse:.4f} mae={mae:.4f} r2={r2:.4f}")
    print(f"  saved       rmse={saved['rmse']:.4f} mae={saved['mae']:.4f} r2={saved['r2']:.4f}")

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

    features = [
        {"label": _display_name(c), "value": float(v), "group": "sequence"}
        for c, v in zip(SEQUENCE_FEATURE_COLUMNS, seq_importance)
    ] + [
        {"label": _display_name(c), "value": float(v), "group": "static"}
        for c, v in zip(STATIC_FEATURE_COLUMNS, static_importance)
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

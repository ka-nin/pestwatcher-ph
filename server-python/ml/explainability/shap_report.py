"""SHAP explainability for the trained BiLSTM outbreak forecaster.

Explains a single live prediction by attributing the model's continuous
output (hoppers/hill or % damage) to the individual features that produced
it — both the per-day sequence features (Tmax, Rainfall, ... at each of the
14 days) and the window-level static features (GDD accumulated, CRF, HP,
...). This is purely post-hoc explanation of an already-trained model; it
never feeds back into training or inference.

Uses shap.GradientExplainer, which supports Keras models with multiple
inputs (this model takes a "sequence_input" and a "static_input"). A
background sample from the pest's own training sequences establishes the
baseline GradientExplainer measures each feature's contribution against.

Run standalone from server-python/ to sanity-check against a live instance:
    .venv/Scripts/python.exe -m ml.explainability.shap_report --pest BPH
"""

import argparse

import numpy as np
import shap

from app.models.bilstm_model import bilstm_forecaster
from ml.bilstm.build_sequences import SEQUENCE_FEATURE_COLUMNS, STATIC_FEATURE_COLUMNS
from ml.config import PEST_PARAMS, SEQUENCES_DIR

BACKGROUND_SAMPLE_SIZE = 40

_explainers: dict[str, shap.GradientExplainer] = {}


def _display_name(column: str) -> str:
    """Turns a raw feature column name into the label style used in the
    thesis's Data Analysis chapter (e.g. "gdd_accum" -> "GDD Accumulated")."""
    overrides = {
        "gdd_accum": "GDD Accumulated",
        "crf": "Cumulative Rainfall Factor (CRF)",
        "hp": "Humidity Persistence (HP)",
        "wsi": "Water Stress Index (WSI)",
        "rainfall_trend": "Rainfall Trend",
        "temp_trend": "Temperature Trend",
        "is_reproductive_target": "Reproductive-Stage Target",
        "reproductive_x_rainfall": "Reproductive Stage x Rainfall",
        "reproductive_x_temp": "Reproductive Stage x Temperature",
        "Tmax": "Max Temperature",
        "Tmin": "Min Temperature",
        "Relative_Humidity": "Relative Humidity",
        "Rainfall": "Rainfall",
        "vpd_daily": "Vapor Pressure Deficit",
        "diurnal_range_daily": "Diurnal Temperature Range",
    }
    if column in overrides:
        return overrides[column]
    if column.startswith("growth_stage_"):
        return f"Growth Stage: {column.removeprefix('growth_stage_').capitalize()}"
    return column


def _get_explainer(pest: str) -> shap.GradientExplainer:
    if pest in _explainers:
        return _explainers[pest]

    data = np.load(SEQUENCES_DIR / f"{pest.lower()}_sequences.npz", allow_pickle=True)
    X_sequence, X_static = data["X_sequence"], data["X_static"]

    rng = np.random.RandomState(0)
    sample_size = min(BACKGROUND_SAMPLE_SIZE, len(X_sequence))
    idx = rng.choice(len(X_sequence), size=sample_size, replace=False)

    scalers = bilstm_forecaster.scalers_for(pest)
    seq_scaler, static_scaler = scalers["sequence_scaler"], scalers["static_scaler"]

    n, w, f = X_sequence[idx].shape
    background_seq = seq_scaler.transform(X_sequence[idx].reshape(-1, f)).reshape(n, w, f)
    background_static = static_scaler.transform(X_static[idx])

    model = bilstm_forecaster.model_for(pest)
    explainer = shap.GradientExplainer(model, [background_seq, background_static])
    _explainers[pest] = explainer
    return explainer


def compute_top_attributions(
    pest: str,
    X_sequence_scaled: np.ndarray,
    X_static_scaled: np.ndarray,
    top_n: int = 7,
) -> list[dict]:
    """Returns the `top_n` (label, value) attributions by absolute SHAP
    value, across both the per-day sequence features and the static
    features, for the single instance in X_sequence_scaled/X_static_scaled
    (shape (1, window_days, n_seq_features) / (1, n_static_features))."""
    explainer = _get_explainer(pest)
    window_days = PEST_PARAMS[pest].crf_window_days

    shap_seq, shap_static = explainer.shap_values([X_sequence_scaled, X_static_scaled])
    # GradientExplainer appends a trailing output-dim axis (regression has 1 output) — drop it.
    shap_seq = np.squeeze(shap_seq, axis=-1)[0]  # (window_days, n_seq_features)
    shap_static = np.squeeze(shap_static, axis=-1)[0]  # (n_static_features,)

    attributions = []
    for day_index in range(window_days):
        day_offset = day_index - (window_days - 1)  # 0 = most recent day, negative = days before
        day_label = "Today" if day_offset == 0 else f"Day {day_offset}"
        for feature_index, column in enumerate(SEQUENCE_FEATURE_COLUMNS):
            value = float(shap_seq[day_index, feature_index])
            attributions.append({"label": f"{day_label} {_display_name(column)}", "value": value})

    for feature_index, column in enumerate(STATIC_FEATURE_COLUMNS):
        value = float(shap_static[feature_index])
        attributions.append({"label": _display_name(column), "value": value})

    attributions.sort(key=lambda a: abs(a["value"]), reverse=True)
    return attributions[:top_n]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = parser.parse_args()

    bilstm_forecaster.load(args.pest)
    data = np.load(SEQUENCES_DIR / f"{args.pest.lower()}_sequences.npz", allow_pickle=True)
    X_sequence, X_static = data["X_sequence"], data["X_static"]

    scalers = bilstm_forecaster.scalers_for(args.pest)
    n, w, f = X_sequence[-1:].shape
    instance_seq = scalers["sequence_scaler"].transform(X_sequence[-1:].reshape(-1, f)).reshape(n, w, f)
    instance_static = scalers["static_scaler"].transform(X_static[-1:])

    for attribution in compute_top_attributions(args.pest, instance_seq, instance_static):
        print(f"{attribution['value']:+.4f}  {attribution['label']}")

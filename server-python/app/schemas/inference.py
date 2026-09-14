from typing import Literal

from pydantic import BaseModel


class ImageInferenceResponse(BaseModel):
    """Response contract for the ResNet-50 optical field surveillance endpoint.

    Kept stable now so the mobile app can integrate against it before the
    real model is trained/loaded — `status` tells the caller whether the
    prediction is real or a placeholder.
    """

    status: Literal["ok", "model_not_loaded"]
    pest_detected: str | None = None
    confidence: float | None = None
    risk_level: Literal["Low", "Moderate", "High", "Critical"] | None = None
    message: str


GrowthStage = Literal["Seedling", "Tillering", "Elongation", "Panicle", "Flowering", "Ripening"]


class DailyWeatherObservation(BaseModel):
    """One day of raw weather + growth stage. The BiLSTM expects a
    consecutive run of these (length = ml.config.PEST_PARAMS[pest].crf_window_days,
    currently 14, most recent day last) — the model computes its own
    engineered features (GDD/CRF/HP/VPD/WSI/...) from these raw values, it
    does not accept pre-aggregated series."""

    date: str
    tmax: float
    tmin: float
    relative_humidity: float
    rainfall: float
    growth_stage: GrowthStage


class ForecastInferenceRequest(BaseModel):
    municipality: str
    pest: Literal["BPH", "RSB"]
    daily_observations: list[DailyWeatherObservation]


class ForecastInferenceResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    predicted_value: float | None = None
    unit: Literal["hoppers_per_hill", "pct_damage"] | None = None
    risk_level: Literal["Low", "Medium", "High"] | None = None
    message: str


class TrajectoryPoint(BaseModel):
    """One point in a multi-day forecast trajectory — see
    GET /api/inference/forecast/trajectory."""

    date: str
    predicted_value: float
    unit: Literal["hoppers_per_hill", "pct_damage"]
    risk_level: Literal["Low", "Medium", "High"]


class TrajectoryResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    points: list[TrajectoryPoint]
    message: str


class ExplanationFeature(BaseModel):
    """One SHAP attribution — see GET /api/inference/forecast/explain."""

    label: str
    value: float


class ExplanationResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    features: list[ExplanationFeature]
    message: str

from typing import Literal

from pydantic import BaseModel

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
    # True when risk_level was bumped one tier by verified farmer reports —
    # see app/decision/report_signal.py. Only set on /forecast/live, which
    # is the only forecast endpoint that knows the municipality to look
    # reports up by.
    adjusted_by_reports: bool = False
    verified_report_count: int = 0


class TrajectoryPoint(BaseModel):
    """One point in a multi-day forecast trajectory — see
    GET /api/inference/forecast/trajectory."""

    date: str
    predicted_value: float
    unit: Literal["hoppers_per_hill", "pct_damage"]
    risk_level: Literal["Low", "Medium", "High"]
    adjusted_by_reports: bool = False


class TrajectoryResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    points: list[TrajectoryPoint]
    message: str


class ImageInferenceResponse(BaseModel):
    """Response contract for the ResNet-50 optical field surveillance endpoint.

    `status` tells the caller whether the image classification itself ran
    ("ok"/"model_not_loaded") or whether neither classifier detected a
    tracked pest ("no_pest_detected") — a real, expected outcome, not an
    error. When a pest IS detected, the endpoint also runs the matching
    BiLSTM forecast for the caller's municipality/growth_stage (a photo
    alone has no time dimension to forecast from — see
    app/models/resnet_model.py's module docstring) — `forecast` carries
    that 14-day trajectory, and is null whenever there's no confirmed pest
    or the caller omitted municipality/growth_stage.
    """

    status: Literal["ok", "model_not_loaded", "no_pest_detected"]
    pest_detected: Literal["BPH", "RSB"] | None = None
    confidence: float | None = None
    risk_level: Literal["Low", "Moderate", "High", "Critical"] | None = None
    message: str
    forecast: TrajectoryResponse | None = None


class ExplanationFeature(BaseModel):
    """One SHAP attribution — see GET /api/inference/forecast/explain."""

    label: str
    value: float


class ExplanationResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    features: list[ExplanationFeature]
    message: str

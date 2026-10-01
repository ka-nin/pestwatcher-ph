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
    # True when predicted_value was shifted to start from the latest verified
    # farmer report — see app/decision/report_anchor.py. Only set on
    # /forecast/live, which is the only single-value endpoint that knows the
    # municipality to look reports up by. verified_report_count is how many
    # matching reports were verified on the report day that drove the shift.
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
    # The single strongest pest (drives the forecast below).
    pest_detected: Literal["BPH", "RSB"] | None = None
    confidence: float | None = None
    risk_level: Literal["Low", "Moderate", "High", "Critical"] | None = None
    message: str
    forecast: TrajectoryResponse | None = None
    # Every pest that cleared its own cutoff, strongest first — a photo with
    # both BPH and RSB lists both here even though only one is pest_detected.
    pests_detected: list[Literal["BPH", "RSB"]] = []
    pest_scores: dict[str, float] = {}
    # Only set when the BPH grid ran (a photo bigger than one insect close-up,
    # see app/preprocessing/tiling.py): tiles scored, and merged hit groups.
    # The group count is an approximate density hint — NOT an exact insect
    # count and NOT hoppers/hill, which comes from verified reports.
    grid_used: bool = False
    grid_tiles: int | None = None
    bph_grid_count: int | None = None


class ExplanationFeature(BaseModel):
    """One SHAP attribution — see GET /api/inference/forecast/explain."""

    label: str
    value: float


class ExplanationResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    features: list[ExplanationFeature]
    message: str


class GapAnalysisDay(BaseModel):
    """One day's side-by-side comparison for
    GET /api/reports/{report_id}/gap-analysis — what the model predicts with
    weather alone (historical) vs. what it would predict if this one
    verified report were allowed to anchor it (report-based). Both values
    are always the plain model's own forecast; the report-based column is
    never what actually shows up live (see app/routers/inference.py's
    _run_forecast docstring — reports no longer shift a live prediction).
    """

    date: str
    historical_value: float | None = None
    historical_risk_level: Literal["Low", "Medium", "High"] | None = None
    report_based_value: float | None = None
    report_based_risk_level: Literal["Low", "Medium", "High"] | None = None
    # How much of the report's influence is still active on this day (1.0 on
    # the report's own date, fading to 0.0 — see app/decision/report_anchor.py).
    report_weight: float = 0.0


class GapAnalysisResponse(BaseModel):
    status: Literal["ok", "model_not_loaded", "report_not_verified"]
    report_id: str
    municipality: str
    pest: Literal["BPH", "RSB"]
    unit: Literal["hoppers_per_hill", "pct_damage"] | None = None
    days: list[GapAnalysisDay]
    # Plain-language takeaway — see app/decision/gap_implication.py.
    implication: str
    message: str

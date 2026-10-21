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
    # True when a recent verified farmer report was fed to the model as its
    # verified-observation input (app/decision/report_anchor.py's
    # find_lagged_observation). Only possible on endpoints that know the
    # municipality to look reports up by. Not a post-hoc shift of the value.
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


class GrowthOutlook(BaseModel):
    """How fast the forecast says the pest is changing — see
    app/decision/outlook.py's growth_outlook. Read off the trajectory, so it
    adds no information beyond the forecast itself."""

    trend: Literal["rising", "falling", "stable"]
    change_per_day: float
    pct_change_per_day: float | None = None
    doubling_days: float | None = None
    days_to_high: int | None = None
    peak_value: float
    peak_date: str
    days_covered: int


class SpreadSummary(BaseModel):
    """Observed extent from technologist-verified reports — see
    app/decision/outlook.py's spread_summary. Observed, not forecast."""

    window_days: int
    recent_reports: int
    recent_hectares: float
    previous_reports: int
    previous_hectares: float
    trend: Literal["spreading", "shrinking", "steady"] | None = None
    mean_photo_coverage_pct: float | None = None


class TrajectoryResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    points: list[TrajectoryPoint]
    outlook: GrowthOutlook | None = None
    spread: SpreadSummary | None = None
    message: str


class ImageInferenceResponse(BaseModel):
    """Response contract for the ResNet-50 optical field surveillance endpoint.

    `status` tells the caller whether the image classification itself ran
    ("ok"/"model_not_loaded") or whether neither tracked classifier detected
    a pest — which splits into two real, expected outcomes rather than one:
    "no_pest_detected" (the photo reads as plain background, confirmed by
    the trained UNKNOWN bug-vs-no-bug classifier — see
    app/models/resnet_model.py's ResnetPrediction.unidentified) and
    "unidentified_pest_detected" (that same classifier found an insect, just
    not BPH or RSB). Neither is an error. When a tracked pest IS detected,
    the endpoint also runs the matching BiLSTM forecast for the caller's
    municipality/growth_stage (a photo alone has no time dimension to
    forecast from — see app/models/resnet_model.py's module docstring) —
    `forecast` carries that 14-day trajectory, and is null whenever there's
    no confirmed pest or the caller omitted municipality/growth_stage.

    `estimated_count`/`estimated_coverage_pct`/`estimated_damage_pct` are the
    photo-derived quantitative estimates from app/models/resnet_model.py's
    ResNet50RegressorBank (the panel-requested redesign) — the same
    suggestions a technologist sees when reviewing a submitted report
    (app/routers/reports.py), surfaced here too so the mobile app's
    immediate scan result can show them. These ARE fed into the `forecast`
    above as a one-off override of the usual verified-reports lookup (see
    app/routers/inference.py's _build_trajectory) — `forecast_reflects_this_photo`
    says whether that happened. They are still UNVERIFIED model outputs: this
    override never writes anything to the database and never changes what
    any other endpoint (GET /forecast/trajectory, the LGU dashboard, SMS
    advisories) returns for this municipality — that only happens once a
    technologist confirms the report this scan produces.
    """

    status: Literal["ok", "model_not_loaded", "no_pest_detected", "unidentified_pest_detected"]
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
    # A legacy density HINT from before ResNet50RegressorBank existed — kept
    # for the grid-used UI copy, but estimated_count below is the real,
    # trained estimate now and should be preferred wherever both are shown.
    grid_used: bool = False
    grid_tiles: int | None = None
    bph_grid_count: int | None = None
    estimated_count: float | None = None
    estimated_coverage_pct: float | None = None
    estimated_damage_pct: float | None = None
    # True when `forecast` above was computed using THIS photo's own
    # estimated_count/estimated_damage_pct (not a technologist-verified
    # report) as its lagged-observation input — lets the mobile UI say "this
    # reflects your photo, not yet confirmed" instead of implying it's the
    # same official forecast an LGU technologist would see for this
    # municipality.
    forecast_reflects_this_photo: bool = False


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
    GET /api/reports/{report_id}/gap-analysis, both from the deployed model:

      historical_*    the forecast with NO verified report as input (the
                      model's "no observation" encoding). This is the
                      baseline ml/validity_test.py compares against the field.
      report_based_*  the forecast with THIS report fed in as the model's
                      verified-observation input (value, age 0, has-report),
                      which is what the live forecast does once a report is
                      verified (app/routers/inference.py's _run_forecast).

    Neither is a post-hoc shift: the old fading report-anchor adjustment was
    removed from the live forecast on 2026-10-20 and from here on 2026-10-21.
    """

    date: str
    historical_value: float | None = None
    historical_risk_level: Literal["Low", "Medium", "High"] | None = None
    report_based_value: float | None = None
    report_based_risk_level: Literal["Low", "Medium", "High"] | None = None


class GapAnalysisResponse(BaseModel):
    status: Literal["ok", "model_not_loaded", "report_not_verified"]
    report_id: str
    municipality: str
    pest: Literal["BPH", "RSB"]
    unit: Literal["hoppers_per_hill", "pct_damage"] | None = None
    days: list[GapAnalysisDay]
    # What the technologist actually confirmed in the field — the ground
    # truth both forecast lines are judged against. Kept separate from the
    # report-based line on purpose: that line is a model output, not the
    # field value.
    verified_value: float | None = None
    verified_risk_level: Literal["Low", "Medium", "High"] | None = None
    # False when the deployed model has no verified-observation input (a
    # 9-static-feature model): the two lines are then identical by
    # construction and the UI says so instead of implying the report had
    # no effect.
    report_is_model_input: bool = False
    # Plain-language takeaway — see app/decision/gap_implication.py.
    implication: str
    message: str

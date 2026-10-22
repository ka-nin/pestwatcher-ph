import uuid
from typing import Literal
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import get_settings
from app.data.municipalities import municipality_coordinates
from app.decision.etl_thresholds import derive_risk_level
from app.decision.outlook import growth_outlook, project_affected_area, spread_summary
from app.decision.report_anchor import find_lagged_observation
from app.models.resnet_model import resnet_classifier, resnet_regressors
from app.routers.weather import fetch_recent_daily_weather
from app.schemas.inference import (
    ExplanationResponse,
    FieldAssessmentResponse,
    ForecastInferenceRequest,
    ForecastInferenceResponse,
    GrowthStage,
    ImageInferenceResponse,
    TrajectoryPoint,
    TrajectoryResponse,
)
from app.models.bilstm_model import DailyObservation, bilstm_forecaster
from ml.config import FORECAST_HORIZON_DAYS, GROWTH_STAGE_BUCKETS, PEST_PARAMS

# Imported lazily inside the /forecast/explain handler below, not here at
# module scope — shap pulls in sklearn.linear_model, whose compiled
# _cd_fast.pyd can be blocked by a locked-down machine's Application
# Control policy. Keeping it out of the startup import chain means that
# only the explain endpoint fails on such a machine, not the whole app.

router = APIRouter(prefix="/api/inference", tags=["inference"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


AFFECTED_CELL_MIN_PCT = 10.0  # a cell counts as "affected" at or above this value
FIELD_GRID_LONG_SIDE_CELLS = 6  # cells along the photo's longer side


def _grid_shape(width: int, height: int) -> tuple[int, int]:
    """Roughly square cells: FIELD_GRID_LONG_SIDE_CELLS along the long side,
    proportionally fewer (at least 2) along the short one."""
    long_cells = FIELD_GRID_LONG_SIDE_CELLS
    short_cells = max(2, round(long_cells * min(width, height) / max(width, height)))
    return (short_cells, long_cells) if width >= height else (long_cells, short_cells)


@router.post("/field-assessment", response_model=FieldAssessmentResponse)
async def assess_field(
    file: UploadFile = File(...),
    pest: Literal["BPH", "RSB"] = Form(...),
    field_size_ha: float | None = Form(None, gt=0, le=1000),
    growth_stage: GrowthStage | None = Form(None),
) -> FieldAssessmentResponse:
    """Severity and extent over a whole-field photo (panel concern: field
    level, not a close-up; regression, not classification).

    The caller names the pest, so no classifier gate runs: the photo is cut
    into a grid of patch-sized cells, the pest's regression model estimates
    each cell, and the result is the mean (% of the photo affected), the share
    of cells affected (how widely), and, given the field size, the affected
    hectares. It uses the pest's FIELD-level damage model, not the patch-level
    coverage/damage models: those were trained on collages of patches and
    measured (2026-10-22) to read the same value on a damaged and a healthy
    field, so they are not used here.

    Nothing is stored and nothing reaches the forecast: this is an unverified
    estimate for a technologist to confirm, like the scan estimates.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type; use JPEG, PNG or WebP.")

    from PIL import Image

    target = "field_damage_pct"
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"field_{uuid.uuid4().hex}{Path(file.filename or 'photo.jpg').suffix or '.jpg'}"
    destination.write_bytes(await file.read())

    try:
        with Image.open(destination) as opened:
            rows, cols = _grid_shape(*opened.size)
        cell_values = resnet_regressors.predict_grid(pest, target, destination, rows, cols)
    finally:
        destination.unlink(missing_ok=True)  # an assessment keeps nothing

    if cell_values is None:
        return FieldAssessmentResponse(
            status="model_not_loaded",
            message=(
                f"No field-level {pest} damage model is installed. It needs training on field photos "
                "(ml/resnet/train_field_damage.py); the patch-level models do not transfer to field photos."
            ),
        )

    flat = [v for row in cell_values for v in row]
    pct_affected = round(sum(flat) / len(flat), 1)
    risk = None
    if pest == "RSB" and growth_stage is not None:
        risk = derive_risk_level(pest, GROWTH_STAGE_BUCKETS[growth_stage], pct_affected)
    return FieldAssessmentResponse(
        status="ok",
        pest=pest,
        target=target,
        rows=rows,
        cols=cols,
        cell_values=[[round(v, 1) for v in row] for row in cell_values],
        pct_affected=pct_affected,
        cells_affected_pct=round(100 * sum(v >= AFFECTED_CELL_MIN_PCT for v in flat) / len(flat), 1),
        field_size_ha=field_size_ha,
        affected_hectares=round(pct_affected / 100 * field_size_ha, 2) if field_size_ha else None,
        risk_level=risk,
        message="Field assessment complete. Unverified estimate: a technologist must confirm it.",
    )


@router.post("/image", response_model=ImageInferenceResponse)
async def infer_image(
    file: UploadFile = File(...),
    municipality: str | None = Form(
        None, description="Farmer's municipality — needed to fetch weather for the 14-day forecast."
    ),
    growth_stage: GrowthStage | None = Form(
        None, description="Current rice growth stage — needed for the forecast's ETL bucketing."
    ),
) -> ImageInferenceResponse:
    """Receives an optical field photo from the mobile app, identifies which
    tracked pest (if any) is present via `resnet_classifier` (two independent
    binary models — see app/models/resnet_model.py), then — if a pest was
    detected — also runs `resnet_regressors` for that pest's quantitative
    estimate (count + coverage for BPH, damage % for RSB), and, if the
    caller supplied municipality/growth_stage, the 14-day BiLSTM forecast
    (GET /forecast/trajectory's same underlying logic) — so the mobile app
    gets one photo-in, full-picture-out response instead of orchestrating
    several separate calls.

    `municipality`/`growth_stage` are optional so a caller that only wants
    the raw classification (no forecast) can omit them — the response's
    `forecast` field is simply null in that case. The estimated_* fields ARE
    fed into this specific forecast (as a one-off override of the usual
    verified-reports lookup — see _build_trajectory's override_lagged_features
    and ImageInferenceResponse.forecast_reflects_this_photo), so the risk the
    farmer sees here can react to their own unverified photo. They still
    never touch the database or any other municipality's forecast; that only
    happens once a technologist confirms the resulting report.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}",
        )

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename or "").suffix or ".jpg"
    destination = upload_dir / f"{uuid.uuid4().hex}{extension}"

    contents = await file.read()
    destination.write_bytes(contents)

    result = resnet_classifier.predict(destination)

    if result is None:
        return ImageInferenceResponse(
            status="model_not_loaded",
            message="ResNet-50 model not loaded yet — image saved for later training/inference",
        )

    if result.label is None:
        if result.unidentified:
            return ImageInferenceResponse(
                status="unidentified_pest_detected",
                message=(
                    "An insect appears to be present, but it did not match our trained BPH/RSB models. "
                    "It may be a different pest — please consult your local agricultural technologist."
                ),
                pest_scores=result.pest_scores,
                grid_used=result.grid_tiles is not None,
                grid_tiles=result.grid_tiles,
                bph_grid_count=result.grid_count,
            )
        return ImageInferenceResponse(
            status="no_pest_detected",
            message="No tracked pest (BPH/RSB) was detected in this photo with sufficient confidence.",
            pest_scores=result.pest_scores,
            grid_used=result.grid_tiles is not None,
            grid_tiles=result.grid_tiles,
            bph_grid_count=result.grid_count,
        )

    # Computed BEFORE the forecast call (unlike before the panel's fix) so
    # this photo's own quantitative estimate can actually feed the
    # trajectory below, instead of the forecast running first with no way
    # to see a number that doesn't exist yet.
    estimated_count = estimated_coverage_pct = estimated_damage_pct = None
    if result.label == "BPH":
        estimated_count = resnet_regressors.predict("BPH", "count", destination)
        estimated_coverage_pct = resnet_regressors.predict("BPH", "coverage_pct", destination)
    elif result.label == "RSB":
        estimated_damage_pct = resnet_regressors.predict("RSB", "damage_pct", destination)

    # The slot's unit must match the pest's own ETL/BiLSTM target unit —
    # hoppers/hill for BPH (estimated_count, not coverage_pct, which is a
    # different quantity: affected area, not density) and % damage for RSB
    # (estimated_damage_pct already matches). Age 0 / recency 1.0: as far as
    # this one-off preview is concerned, this estimate is "observed today."
    photo_lagged_features: tuple[float, float, float] | None = None
    if result.label == "BPH" and estimated_count is not None:
        photo_lagged_features = (estimated_count, 0.0, 1.0)
    elif result.label == "RSB" and estimated_damage_pct is not None:
        photo_lagged_features = (estimated_damage_pct, 0.0, 1.0)

    forecast: TrajectoryResponse | None = None
    if municipality and growth_stage:
        forecast = _build_trajectory(
            municipality, result.label, growth_stage, days=13, override_lagged_features=photo_lagged_features
        )

    return ImageInferenceResponse(
        status="ok",
        pest_detected=result.label,
        estimated_count=estimated_count,
        estimated_coverage_pct=estimated_coverage_pct,
        estimated_damage_pct=estimated_damage_pct,
        confidence=result.confidence,
        risk_level=result.risk_level,
        message="Prediction successful",
        forecast=forecast,
        forecast_reflects_this_photo=photo_lagged_features is not None,
        pests_detected=result.pests_detected,
        pest_scores=result.pest_scores,
        grid_used=result.grid_tiles is not None,
        grid_tiles=result.grid_tiles,
        bph_grid_count=result.grid_count,
    )


def _window_for_target(
    pest: str, target_date: date, growth_stage: GrowthStage, weather_by_date: dict[str, dict]
) -> list[DailyObservation] | None:
    """The 14-day weather window the model needs to predict `target_date`
    (it ends FORECAST_HORIZON_DAYS before it). None if the fetched weather
    doesn't reach back far enough."""
    window_days = PEST_PARAMS[pest].crf_window_days
    window_end = target_date - timedelta(days=FORECAST_HORIZON_DAYS)
    window_dates = [(window_end - timedelta(days=window_days - 1 - i)).isoformat() for i in range(window_days)]

    if not all(d in weather_by_date for d in window_dates):
        return None

    return [
        DailyObservation(
            tmax=weather_by_date[d]["tmax"],
            tmin=weather_by_date[d]["tmin"],
            relative_humidity=weather_by_date[d]["relative_humidity"],
            rainfall=weather_by_date[d]["rainfall"],
            growth_stage=growth_stage,
        )
        for d in window_dates
    ]


def _run_forecast(
    pest: str, window: list[DailyObservation], municipality: str | None = None
) -> ForecastInferenceResponse:
    """Shared by both endpoints below: predict, then apply the (separate,
    non-learned) ETL bucketing — see app/decision/etl_thresholds.py.

    A verified report still never DIRECTLY overwrites predicted_value the
    way the old report-anchor fade did — there is no post-hoc shift here.
    What changed (the panel's redesign): the model itself now has a lagged-
    observation INPUT (app/decision/report_anchor.py's
    find_lagged_observation(), trained via ml/bilstm/build_sequences.py
    --features lagged), so a recent verified report legitimately influences
    the forecast by being part of what the model was asked to reason about —
    the same way a weather input does — rather than by adjusting its output
    afterward. `municipality` is optional because POST /forecast (raw
    observations, no municipality in the payload) has no report context to
    look up; it gets the model's own "no recent observation" default instead
    of an error.
    """
    growth_stage_bucket = GROWTH_STAGE_BUCKETS[window[-1].growth_stage]
    lagged_features = None
    if municipality is not None:
        lagged_features = find_lagged_observation(municipality, pest, date.today(), growth_stage_bucket)

    result = bilstm_forecaster.predict(pest, window, lagged_features)

    if result is None:
        return ForecastInferenceResponse(
            status="model_not_loaded",
            message=f"BiLSTM model for {pest} not loaded yet — placeholder response",
        )

    value = result.predicted_value
    risk_level = derive_risk_level(pest, growth_stage_bucket, value)

    return ForecastInferenceResponse(
        status="ok",
        predicted_value=value,
        unit=result.unit,
        risk_level=risk_level,
        message="Forecast successful",
        adjusted_by_reports=lagged_features is not None and lagged_features[2] == 1.0,
        verified_report_count=1 if lagged_features is not None and lagged_features[2] == 1.0 else 0,
    )


@router.post("/forecast", response_model=ForecastInferenceResponse)
def infer_forecast(payload: ForecastInferenceRequest) -> ForecastInferenceResponse:
    """Takes a window of raw daily weather + growth stage observations and
    returns a continuous outbreak forecast (hoppers/hill for BPH, % damage
    for RSB), plus the ETL-derived Low/Medium/High level applied to it.

    The forecast itself is learned (bilstm_forecaster, app/models/bilstm_model.py);
    the risk level is not (app/decision/etl_thresholds.py) — kept as two
    separate steps per the panel's fix #1, so the model can't drift from the
    fixed PhilRice/DA-RCPC decision thresholds.

    Caller supplies the daily observations directly — use this when weather
    has already been fetched/logged elsewhere. For a live fetch from
    today's weather, see GET /forecast/live below.
    """
    expected_days = PEST_PARAMS[payload.pest].crf_window_days
    if len(payload.daily_observations) != expected_days:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{payload.pest} requires exactly {expected_days} consecutive daily "
                f"observations, got {len(payload.daily_observations)}."
            ),
        )

    window = [
        DailyObservation(
            tmax=obs.tmax,
            tmin=obs.tmin,
            relative_humidity=obs.relative_humidity,
            rainfall=obs.rainfall,
            growth_stage=obs.growth_stage,
        )
        for obs in payload.daily_observations
    ]

    return _run_forecast(payload.pest, window)


def _live_forecast(municipality: str, pest: str, growth_stage: GrowthStage) -> ForecastInferenceResponse:
    """Shared by GET /forecast/live and the superadmin cross-municipality
    overview (app/routers/admin.py) so both run the exact same pipeline.

    See _run_forecast's docstring for how a verified report now reaches the
    model (as a lagged-observation input, looked up here by municipality) —
    only the weather window itself is fetched below.
    """
    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest].crf_window_days
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=window_days)

    window = [
        DailyObservation(
            tmax=day["tmax"],
            tmin=day["tmin"],
            relative_humidity=day["relative_humidity"],
            rainfall=day["rainfall"],
            growth_stage=growth_stage,
        )
        for day in daily_weather[-window_days:]
    ]

    return _run_forecast(pest, window, municipality)


@router.get("/forecast/live", response_model=ForecastInferenceResponse)
def infer_forecast_live(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(
        ...,
        description=(
            "Current rice growth stage for this field. Applied to every day in "
            "the fetched window — weather APIs have no concept of crop growth "
            "stage, so this has to come from LGU/farmer-reported data, not "
            "from the live fetch."
        ),
    ),
) -> ForecastInferenceResponse:
    """Live version of /forecast: fetches the actual past N days of weather
    for `municipality` from Open-Meteo (N = ml.config.PEST_PARAMS[pest].crf_window_days,
    currently 14) instead of requiring the caller to supply it, then runs
    the same predict + ETL-bucket pipeline as /forecast.
    """
    return _live_forecast(municipality, pest, growth_stage)


def _build_trajectory(
    municipality: str,
    pest: str,
    growth_stage: GrowthStage,
    days: int,
    override_lagged_features: tuple[float, float, float] | None = None,
) -> TrajectoryResponse:
    """Shared by GET /forecast/trajectory and POST /image (once a pest is
    detected in a photo, its 14-day trajectory is fetched the same way) so
    both run the exact same pipeline.

    Key trick: because the model's forecast horizon (FORECAST_HORIZON_DAYS,
    currently 14) is >= the number of future days requested here, EVERY
    window this needs — even the one whose target is `days` days from now —
    ends on or before today. So the whole trajectory can be built from
    already-observed weather; no forecast-weather API is needed, only the
    same past-days fetch /forecast/live uses, just a longer stretch of it.

    `override_lagged_features` lets POST /image feed THIS photo's own
    just-computed regression estimate (count/damage_pct — see infer_image)
    into the lagged-observation slot instead of looking one up by
    municipality. It never touches the database and it never affects
    GET /forecast/trajectory (which always passes None and keeps using
    find_lagged_observation's verified-only lookup) — it exists only so the
    one-off trajectory shown back to the farmer who just took this photo can
    react to their own unverified estimate, per the panel's ask that the
    predicted risk actually depend on the photo's count/coverage, not just
    weather. The number only becomes a real, system-of-record input (and
    something every other municipality view can see) once a technologist
    confirms the report it came from.
    """
    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    today = date.today()

    # Generous on purpose: the last target's window could start as far back
    # as (today - horizon - window_days + 1); this fetch covers that plus
    # margin rather than computing the minimum.
    fetch_days = PEST_PARAMS[pest].crf_window_days + days + FORECAST_HORIZON_DAYS
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=fetch_days)
    weather_by_date = {day["date"]: day for day in daily_weather}

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]
    # Looked up once per trajectory (not once per point): the lagged
    # observation is relative to `today`, same reference point regardless of
    # which future day each trajectory point targets — see _run_forecast's
    # docstring for what this represents. An override (this photo's own
    # fresh, unverified estimate) always wins over the verified-reports
    # lookup when the caller supplies one.
    lagged_features = override_lagged_features
    if lagged_features is None:
        lagged_features = find_lagged_observation(municipality, pest, today, growth_stage_bucket)

    points: list[TrajectoryPoint] = []
    for offset in range(days):
        target_date = today + timedelta(days=offset)
        window = _window_for_target(pest, target_date, growth_stage, weather_by_date)
        if window is None:
            continue  # not enough fetched history for this point — skip rather than fail the whole trajectory

        result = bilstm_forecaster.predict(pest, window, lagged_features)
        if result is None:
            return TrajectoryResponse(
                status="model_not_loaded",
                points=[],
                message=f"BiLSTM model for {pest} not loaded yet",
            )

        value = result.predicted_value

        points.append(
            TrajectoryPoint(
                date=target_date.isoformat(),
                predicted_value=value,
                unit=result.unit,
                risk_level=derive_risk_level(pest, growth_stage_bucket, value),
                adjusted_by_reports=lagged_features[2] == 1.0,
            )
        )

    spread = spread_summary(municipality, pest, today)
    for point, hectares in zip(points, project_affected_area(points, spread["recent_hectares"])):
        point.projected_affected_ha = hectares

    return TrajectoryResponse(
        status="ok",
        points=points,
        outlook=growth_outlook(points, pest),
        spread=spread,
        message="Trajectory forecast successful",
    )


@router.get("/forecast/trajectory", response_model=TrajectoryResponse)
def infer_forecast_trajectory(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(
        ...,
        description="Applied to every day across every window — see /forecast/live for why.",
    ),
    days: int = Query(13, ge=1, le=14, description="How many future days to forecast, starting today."),
) -> TrajectoryResponse:
    """Multi-day forecast trajectory, for charting a projected outbreak curve
    (e.g. May 17 -> May 29) rather than a single point. See _build_trajectory
    for the actual logic, shared with POST /image.
    """
    return _build_trajectory(municipality, pest, growth_stage, days)


@router.get("/forecast/explain", response_model=ExplanationResponse)
def infer_forecast_explain(
    municipality: str = Query(..., description="Must match a municipality in app/data/lgu_users.py"),
    pest: str = Query(..., pattern="^(BPH|RSB)$"),
    growth_stage: GrowthStage = Query(..., description="Same growth-stage semantics as /forecast/live."),
    top_n: int = Query(7, ge=1, le=20),
) -> ExplanationResponse:
    """SHAP feature attributions for today's live forecast — explains why
    the model produced the value /forecast/live returns for the same
    municipality/pest/growth_stage, not a separate prediction.

    Post-hoc explanation only (ml/explainability/shap_report.py) — this
    never feeds back into the model or the ETL thresholds.
    """
    if not bilstm_forecaster.is_loaded(pest):
        return ExplanationResponse(
            status="model_not_loaded",
            features=[],
            message=f"BiLSTM model for {pest} not loaded yet",
        )

    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest].crf_window_days
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=window_days)

    window = [
        DailyObservation(
            tmax=day["tmax"],
            tmin=day["tmin"],
            relative_humidity=day["relative_humidity"],
            rainfall=day["rainfall"],
            growth_stage=growth_stage,
        )
        for day in daily_weather
    ]

    from ml.explainability.shap_report import compute_top_attributions

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]
    lagged_features = find_lagged_observation(municipality, pest, date.today(), growth_stage_bucket)
    X_sequence_scaled, X_static_scaled = bilstm_forecaster.build_model_inputs(pest, window, lagged_features)
    attributions = compute_top_attributions(pest, X_sequence_scaled, X_static_scaled, top_n=top_n)

    return ExplanationResponse(status="ok", features=attributions, message="Explanation successful")

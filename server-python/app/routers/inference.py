import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import get_settings
from app.data.lgu_users import municipality_coordinates
from app.decision.etl_thresholds import derive_risk_level
from app.decision.report_signal import apply_adjustment
from app.models.resnet_model import resnet_classifier
from app.routers.weather import fetch_recent_daily_weather
from app.schemas.inference import (
    ExplanationResponse,
    ForecastInferenceRequest,
    ForecastInferenceResponse,
    GrowthStage,
    ImageInferenceResponse,
    TrajectoryPoint,
    TrajectoryResponse,
)
from app.models.bilstm_model import DailyObservation, bilstm_forecaster
from ml.config import FORECAST_HORIZON_DAYS, GROWTH_STAGE_BUCKETS, PEST_PARAMS
from ml.explainability.shap_report import compute_top_attributions

router = APIRouter(prefix="/api/inference", tags=["inference"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


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
    detected AND the caller supplied municipality/growth_stage — immediately
    runs that pest's 14-day BiLSTM forecast (GET /forecast/trajectory's same
    underlying logic) so the mobile app gets one photo-in, full-picture-out
    response instead of orchestrating two separate calls.

    `municipality`/`growth_stage` are optional so a caller that only wants
    the raw classification (no forecast) can omit them — the response's
    `forecast` field is simply null in that case.
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
        return ImageInferenceResponse(
            status="no_pest_detected",
            message="No tracked pest (BPH/RSB) was detected in this photo with sufficient confidence.",
        )

    forecast: TrajectoryResponse | None = None
    if municipality and growth_stage:
        forecast = _build_trajectory(municipality, result.label, growth_stage, days=13)

    return ImageInferenceResponse(
        status="ok",
        pest_detected=result.label,
        confidence=result.confidence,
        risk_level=result.risk_level,
        message="Prediction successful",
        forecast=forecast,
    )


def _run_forecast(pest: str, window: list[DailyObservation], municipality: str) -> ForecastInferenceResponse:
    """Shared by both endpoints below: predict, apply the (separate,
    non-learned) ETL bucketing — see app/decision/etl_thresholds.py — then
    let LGU-verified reports for this municipality bump that level one tier
    if there's enough recent corroborated ground truth (app/decision/report_signal.py).
    """
    result = bilstm_forecaster.predict(pest, window)

    if result is None:
        return ForecastInferenceResponse(
            status="model_not_loaded",
            message=f"BiLSTM model for {pest} not loaded yet — placeholder response",
        )

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[window[-1].growth_stage]
    risk_level = derive_risk_level(pest, growth_stage_bucket, result.predicted_value)
    adjusted_level, signal = apply_adjustment(risk_level, municipality, pest)

    return ForecastInferenceResponse(
        status="ok",
        predicted_value=result.predicted_value,
        unit=result.unit,
        risk_level=adjusted_level,
        message="Forecast successful",
        adjusted_by_reports=adjusted_level != risk_level,
        verified_report_count=signal.verified_report_count,
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

    return _run_forecast(payload.pest, window, payload.municipality)


def _live_forecast(municipality: str, pest: str, growth_stage: GrowthStage) -> ForecastInferenceResponse:
    """Shared by GET /forecast/live and the superadmin cross-municipality
    overview (app/routers/admin.py) so both run the exact same pipeline."""
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


def _build_trajectory(municipality: str, pest: str, growth_stage: GrowthStage, days: int) -> TrajectoryResponse:
    """Shared by GET /forecast/trajectory and POST /image (once a pest is
    detected in a photo, its 14-day trajectory is fetched the same way) so
    both run the exact same pipeline.

    Key trick: because the model's forecast horizon (FORECAST_HORIZON_DAYS,
    currently 14) is >= the number of future days requested here, EVERY
    window this needs — even the one whose target is `days` days from now —
    ends on or before today. So the whole trajectory can be built from
    already-observed weather; no forecast-weather API is needed, only the
    same past-days fetch /forecast/live uses, just a longer stretch of it.
    """
    coordinates = municipality_coordinates(municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest].crf_window_days
    today = date.today()

    # Generous on purpose: the last target's window could start as far back
    # as (today - horizon - window_days + 1); this fetch covers that plus
    # margin rather than computing the exact minimum.
    fetch_days = window_days + days + FORECAST_HORIZON_DAYS
    daily_weather = fetch_recent_daily_weather(latitude, longitude, days=fetch_days)
    weather_by_date = {day["date"]: day for day in daily_weather}

    points: list[TrajectoryPoint] = []
    for offset in range(days):
        target_date = today + timedelta(days=offset)
        window_end = target_date - timedelta(days=FORECAST_HORIZON_DAYS)
        window_dates = [
            (window_end - timedelta(days=window_days - 1 - i)).isoformat() for i in range(window_days)
        ]

        if not all(d in weather_by_date for d in window_dates):
            continue  # not enough fetched history for this point — skip rather than fail the whole trajectory

        window = [
            DailyObservation(
                tmax=weather_by_date[d]["tmax"],
                tmin=weather_by_date[d]["tmin"],
                relative_humidity=weather_by_date[d]["relative_humidity"],
                rainfall=weather_by_date[d]["rainfall"],
                growth_stage=growth_stage,
            )
            for d in window_dates
        ]

        result = bilstm_forecaster.predict(pest, window)
        if result is None:
            return TrajectoryResponse(
                status="model_not_loaded",
                points=[],
                message=f"BiLSTM model for {pest} not loaded yet",
            )

        growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]
        risk_level = derive_risk_level(pest, growth_stage_bucket, result.predicted_value)
        adjusted_level, report_signal = apply_adjustment(risk_level, municipality, pest)
        points.append(
            TrajectoryPoint(
                date=target_date.isoformat(),
                predicted_value=result.predicted_value,
                unit=result.unit,
                risk_level=adjusted_level,
                adjusted_by_reports=adjusted_level != risk_level,
            )
        )

    return TrajectoryResponse(status="ok", points=points, message="Trajectory forecast successful")


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

    X_sequence_scaled, X_static_scaled = bilstm_forecaster.build_model_inputs(pest, window)
    attributions = compute_top_attributions(pest, X_sequence_scaled, X_static_scaled, top_n=top_n)

    return ExplanationResponse(status="ok", features=attributions, message="Explanation successful")

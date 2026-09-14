import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.data.lgu_users import municipality_coordinates
from app.decision.etl_thresholds import derive_risk_level
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
async def infer_image(file: UploadFile = File(...)) -> ImageInferenceResponse:
    """Receives an optical field image from the mobile app for pest/disease detection.

    Wired up to `resnet_classifier`, which is currently a stub — see
    app/models/resnet_model.py for where to load the trained ResNet-50 weights.
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

    return ImageInferenceResponse(
        status="ok" if result is not None else "model_not_loaded",
        pest_detected=result.label if result else None,
        confidence=result.confidence if result else None,
        risk_level=result.risk_level if result else None,
        message=(
            "Prediction successful"
            if result
            else "ResNet-50 model not loaded yet — image saved for later training/inference"
        ),
    )


def _run_forecast(pest: str, window: list[DailyObservation]) -> ForecastInferenceResponse:
    """Shared by both endpoints below: predict, then apply the (separate,
    non-learned) ETL bucketing — see app/decision/etl_thresholds.py.
    """
    result = bilstm_forecaster.predict(pest, window)

    if result is None:
        return ForecastInferenceResponse(
            status="model_not_loaded",
            message=f"BiLSTM model for {pest} not loaded yet — placeholder response",
        )

    growth_stage_bucket = GROWTH_STAGE_BUCKETS[window[-1].growth_stage]
    risk_level = derive_risk_level(pest, growth_stage_bucket, result.predicted_value)

    return ForecastInferenceResponse(
        status="ok",
        predicted_value=result.predicted_value,
        unit=result.unit,
        risk_level=risk_level,
        message="Forecast successful",
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

    return _run_forecast(pest, window)


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
    (e.g. May 17 -> May 29) rather than a single point.

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
        points.append(
            TrajectoryPoint(
                date=target_date.isoformat(),
                predicted_value=result.predicted_value,
                unit=result.unit,
                risk_level=risk_level,
            )
        )

    return TrajectoryResponse(status="ok", points=points, message="Trajectory forecast successful")


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

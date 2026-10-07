"""SuperAdmin-only endpoints: LGU account management, cross-municipality
overview, and a read-only view of the fixed ETL thresholds.

Every endpoint here requires a valid SuperAdmin JWT (see app/dependencies.py)
— this is the one part of the API that actually enforces authorization;
the rest of the API (inference/reports/weather) still trusts the caller,
same as before this router was added.
"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.data.lgu_users import add_lgu_user, delete_lgu_user, find_lgu_user
from app.data.lgu_users import list_lgu_users as fetch_lgu_users
from app.data.lgu_users import update_lgu_user as persist_lgu_user_update
from app.data.model_insights import _read_json, build_model_insights
from app.data.municipalities import upsert_municipality
from app.decision.etl_thresholds import PEST_THRESHOLDS, derive_risk_level
from app.dependencies import require_superadmin
from app.models.bilstm_model import DailyObservation, bilstm_forecaster, raw_baseline_forecaster
from app.models.resnet_model import resnet_classifier
from app.routers.inference import ALLOWED_CONTENT_TYPES, _live_forecast
from app.schemas.admin import EtlThresholdsResponse, MunicipalityOverview, OverviewResponse
from app.schemas.auth import CreateLguUserRequest, LguAccountAdminResponse, LguUser, UpdateLguUserRequest
from app.schemas.simulation import (
    SimulationForecastRequest,
    SimulationForecastResponse,
    SimulationImageResult,
    SimulationModelResult,
)
from app.security import hash_password
from ml.config import GROWTH_STAGE_BUCKETS, PEST_PARAMS

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_superadmin)])

# Growth stage isn't tracked per-municipality anywhere yet (it's normally
# reported per-field by the LGU/farmer) — the overview uses a fixed stage
# so every municipality's forecast is at least comparable to each other.
OVERVIEW_GROWTH_STAGE = "Tillering"


def _to_admin_response(user: LguUser) -> LguAccountAdminResponse:
    return LguAccountAdminResponse(
        username=user.username,
        roleLevel=user.role_level,
        province=user.province,
        municipality=user.municipality,
        latitude=user.latitude,
        longitude=user.longitude,
        isActive=user.is_active,
    )


@router.get("/lgu-users", response_model=list[LguAccountAdminResponse])
def list_lgu_users() -> list[LguAccountAdminResponse]:
    return [_to_admin_response(u) for u in fetch_lgu_users()]


@router.post("/lgu-users", response_model=LguAccountAdminResponse, status_code=201)
def create_lgu_user(payload: CreateLguUserRequest) -> LguAccountAdminResponse:
    if find_lgu_user(payload.username) is not None:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' is already taken")

    user = LguUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role_level=payload.role_level,
        province=payload.province,
        municipality=payload.municipality,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    add_lgu_user(user)
    # Registers/refreshes this municipality in the shared registry (see
    # app/data/municipalities.py) so it shows up for weather lookups and
    # the mobile app's picker even before any farmer account exists there.
    upsert_municipality(user.municipality, user.province, user.latitude, user.longitude)
    return _to_admin_response(user)


@router.patch("/lgu-users/{username}", response_model=LguAccountAdminResponse)
def update_lgu_user(username: str, payload: UpdateLguUserRequest) -> LguAccountAdminResponse:
    updated = persist_lgu_user_update(
        username,
        password_hash=hash_password(payload.password) if payload.password is not None else None,
        role_level=payload.role_level,
        province=payload.province,
        municipality=payload.municipality,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_active=payload.is_active,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No LGU user '{username}'")
    upsert_municipality(updated.municipality, updated.province, updated.latitude, updated.longitude)
    return _to_admin_response(updated)


@router.delete("/lgu-users/{username}", status_code=204)
def remove_lgu_user(username: str) -> None:
    if not delete_lgu_user(username):
        raise HTTPException(status_code=404, detail=f"No LGU user '{username}'")


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    """One BPH + RSB live forecast per municipality on file — the
    superadmin's cross-municipality view. Reuses the exact same pipeline
    /api/inference/forecast/live uses per municipality (see
    app/routers/inference.py's _live_forecast), so results always match
    what each LGU technician sees for their own municipality.
    """
    seen: set[str] = set()
    rows: list[MunicipalityOverview] = []

    for user in fetch_lgu_users():
        if user.municipality in seen:
            continue
        seen.add(user.municipality)

        rows.append(
            MunicipalityOverview(
                province=user.province,
                municipality=user.municipality,
                bph=_live_forecast(user.municipality, "BPH", OVERVIEW_GROWTH_STAGE),
                rsb=_live_forecast(user.municipality, "RSB", OVERVIEW_GROWTH_STAGE),
            )
        )

    return OverviewResponse(growthStageUsed=OVERVIEW_GROWTH_STAGE, municipalities=rows)


@router.get("/etl-thresholds", response_model=EtlThresholdsResponse)
def get_etl_thresholds() -> EtlThresholdsResponse:
    return EtlThresholdsResponse(
        thresholds={
            pest: {
                stage: {"lowMax": band.low_max, "highMin": band.high_min}
                for stage, band in stages.items()
            }
            for pest, stages in PEST_THRESHOLDS.items()
        }
    )


@router.get("/model-insights")
def get_model_insights() -> dict[str, Any]:
    """Model status plus the saved evaluation results (ResNet-50 metrics and
    BPH grid test, BiLSTM regression metrics, test predictions and SHAP
    summary) behind admin-web's Model Insights page. Read from the artifacts
    next to the weights (see app/data/model_insights.py) — nothing is
    recomputed per request."""
    return build_model_insights()


# ---- Simulation page: manual weather window (+ optional photo) run through
# the deployed engineered model AND the raw-feature baseline side by side.


def _simulation_result(forecaster, pest: str, window: list[DailyObservation]) -> SimulationModelResult:
    if not forecaster.is_loaded(pest):
        return SimulationModelResult(status="model_not_loaded")

    result = forecaster.predict(pest, window)
    growth_stage_bucket = GROWTH_STAGE_BUCKETS[window[-1].growth_stage]
    risk_level = derive_risk_level(pest, growth_stage_bucket, result.predicted_value)
    return SimulationModelResult(
        status="ok",
        predicted_value=result.predicted_value,
        unit=result.unit,
        risk_level=risk_level,
    )


@router.post("/simulation/forecast", response_model=SimulationForecastResponse)
def run_simulation_forecast(payload: SimulationForecastRequest) -> SimulationForecastResponse:
    """Runs one manually-entered 14-day weather window through the deployed
    engineered-feature BiLSTM and the raw-feature baseline (ml/bilstm/train.py
    --features raw), so a panelist/technician can see both models' live
    prediction and risk level for the exact same hypothetical window.

    `heldOutMetrics` is the already-computed engineered-vs-raw comparison
    from ml/bilstm/compare_features.py (5-fold expanding-window CV, paired
    significance tests) — historical evidence shown alongside this one-off
    run, not recomputed per request.
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

    folder = PEST_PARAMS[payload.pest].bilstm_weights_path.parent
    held_out = _read_json(folder / f"bilstm_{payload.pest.lower()}_feature_comparison.json")

    return SimulationForecastResponse(
        pest=payload.pest,
        engineered=_simulation_result(bilstm_forecaster, payload.pest, window),
        raw=_simulation_result(raw_baseline_forecaster, payload.pest, window),
        heldOutMetrics=held_out,
    )


@router.post("/simulation/image", response_model=SimulationImageResult)
async def run_simulation_image(file: UploadFile = File(...)) -> SimulationImageResult:
    """Runs a manually-uploaded photo through the real ResNet-50 classifiers
    (same app/models/resnet_model.py used by the farmer app's live pest
    scan — see POST /api/inference/image) and attaches each detected pest's
    held-out test metrics (accuracy/precision/recall/F1, confusion matrix)
    from Model Insights as context."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {file.content_type}")

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename or "").suffix or ".jpg"
    destination = upload_dir / f"sim-{uuid.uuid4().hex}{extension}"
    destination.write_bytes(await file.read())

    result = resnet_classifier.predict(destination)

    if result is None:
        return SimulationImageResult(status="model_not_loaded")

    def metrics_for(pest: str) -> dict | None:
        return _read_json(PEST_PARAMS[pest].bilstm_weights_path.parent / f"resnet50_{pest.lower()}_test_metrics.json")

    held_out = {pest: metrics_for(pest) for pest in result.pest_scores} if result.pest_scores else None

    if result.label is None:
        return SimulationImageResult(
            status="no_pest_detected",
            pest_scores=result.pest_scores,
            heldOutMetrics=held_out,
        )

    return SimulationImageResult(
        status="ok",
        pest_detected=result.label,
        confidence=result.confidence,
        pests_detected=result.pests_detected,
        pest_scores=result.pest_scores,
        heldOutMetrics=held_out,
    )

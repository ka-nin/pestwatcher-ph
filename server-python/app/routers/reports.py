import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config import get_settings
from app.data import reports_store
from app.data.lgu_users import find_lgu_user
from app.data.municipalities import municipality_coordinates
from app.decision.etl_thresholds import derive_risk_level
from app.decision.gap_implication import describe_gap
from app.decision.pest_matching import derive_pest_code
from app.decision.report_anchor import anchor_from_report
from app.dependencies import require_lgu
from app.models.bilstm_model import bilstm_forecaster
from app.models.resnet_model import resnet_classifier, resnet_regressors
from app.rate_limit import RateLimitExceeded, RateLimiter
from app.routers.inference import _assess_photo, _damage_found, _window_for_target
from app.routers.weather import fetch_daily_weather_range
from app.security import TokenPayload
from app.schemas.inference import GapAnalysisDay, GapAnalysisResponse
from app.schemas.reports import ReportRecord, ReportResponse, ReportStatusUpdate
from ml.config import FORECAST_HORIZON_DAYS, GROWTH_STAGE_BUCKETS, PEST_PARAMS

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Same allowlist as /api/inference/image (app/routers/inference.py) — kept
# duplicated rather than imported to avoid coupling the two routers over
# what's otherwise an unrelated constant.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Anti-spam guardrails for the public, farmer-facing submission endpoint —
# there's no farmer login to rate-limit by account, so this throttles by
# requesting IP instead. A genuine farmer with a real outbreak on hand
# won't hit either limit; both exist to stop a script (or a mis-tapping
# button) from flooding an LGU's review queue or artificially inflating
# app/decision/report_anchor.py's verified-report forecast anchor.
REPORT_RATE_LIMIT_MAX = 5
REPORT_RATE_LIMIT_WINDOW_SECONDS = 10 * 60
DUPLICATE_REPORT_WINDOW_MINUTES = 10

_report_rate_limiter = RateLimiter(
    max_requests=REPORT_RATE_LIMIT_MAX, window_seconds=REPORT_RATE_LIMIT_WINDOW_SECONDS
)


@router.get("", response_model=list[ReportRecord])
def list_reports(province: str | None = None, municipality: str | None = None) -> list[ReportRecord]:
    """Farmer-submitted sightings, most recent first.

    `province` backs the mobile app's broader "regional alerts" feed
    (neighboring municipalities included); `municipality` is what
    admin-web's tenant-scoped Reports tab uses — an LGU technician should
    only ever see sightings from their own municipality, not the whole
    province. Both are optional and combinable.
    """
    return reports_store.list_reports(province=province, municipality=municipality)


@router.post("", response_model=ReportResponse)
async def submit_report(
    request: Request,
    pest_type: str = Form(...),
    severity: str = Form(...),
    province: str = Form(...),
    municipality: str = Form(...),
    date_spotted: str = Form(...),
    crop_growth_stage: str = Form("Tillering"),
    username: str = Form("Anonymous Farmer"),
    notes: str = Form(""),
    area_affected: float | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    estimated_value: float | None = Form(None),
    file: UploadFile | None = File(None),
) -> ReportResponse:
    """Farmer-submitted pest sighting — multipart/form-data so an optional
    photo can ride along with it (the mobile app's primary "report with
    photo" path) rather than requiring a separate upload call. A manual,
    photo-less report (the fallback path) is the same endpoint with `file`
    omitted. Persisted to the `reports` Postgres table (app/data/reports_store.py).
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        _report_rate_limiter.check(client_ip)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Too many reports submitted — please wait {round(exc.retry_after_seconds)}s and try again.",
        ) from exc

    duplicate_cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_REPORT_WINDOW_MINUTES)
    ).isoformat()
    if reports_store.count_recent_similar_reports(username, municipality, pest_type, duplicate_cutoff) > 0:
        raise HTTPException(
            status_code=409,
            detail="You already reported this pest sighting recently — please wait before submitting again.",
        )

    photo_path: str | None = None
    ai_pest_detected: str | None = None
    ai_confidence: float | None = None
    ai_suggested_count: float | None = None
    ai_suggested_coverage_pct: float | None = None
    ai_suggested_damage_pct: float | None = None

    if file is not None:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=415, detail=f"Unsupported content type: {file.content_type}")

        settings = get_settings()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(file.filename or "").suffix or ".jpg"
        photo_path = f"{uuid.uuid4().hex}{extension}"
        contents = await file.read()
        (upload_dir / photo_path).write_bytes(contents)

        # Best-effort: predict() returns None until at least one pest's
        # weights are loaded (app/models/resnet_model.py) — a report with a
        # photo but no AI read is a normal, expected state, same as
        # /api/inference/image's "model_not_loaded". Runs every loaded
        # pest's classifier and keeps whichever fires strongest, since a
        # report photo isn't necessarily of the pest the farmer picked.
        # label stays None when neither pest was detected.
        prediction = resnet_classifier.predict(upload_dir / photo_path)
        if prediction is not None:
            ai_pest_detected = prediction.label
            ai_confidence = prediction.confidence

            # Suggestions only — shown to the technologist during review,
            # never written to estimated_value/area_affected directly. Same
            # trust gate as the pest-identity call above: a human still
            # confirms or corrects the actual number (see ReportDB's
            # ai_suggested_* docstring in app/db_models.py).
            if ai_pest_detected == "BPH":
                ai_suggested_count = resnet_regressors.predict("BPH", "count", upload_dir / photo_path)
                ai_suggested_coverage_pct = resnet_regressors.predict("BPH", "coverage_pct", upload_dir / photo_path)
            elif ai_pest_detected == "RSB":
                ai_suggested_damage_pct = resnet_regressors.predict("RSB", "damage_pct", upload_dir / photo_path)
            elif not prediction.unidentified:
                # No insect in frame: a field photo can still show stem-borer damage
                # (same rule as the scan), which is how RSB is measured. The severity
                # is the suggestion; the technologist still confirms the pest and number.
                damage = _assess_photo("RSB", upload_dir / photo_path)
                if damage is not None and _damage_found(damage):
                    ai_pest_detected = "RSB"
                    ai_suggested_damage_pct = damage.pct_affected

    record = ReportRecord(
        id=uuid.uuid4().hex,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        username=username,
        pest_type=pest_type,
        pest_code=derive_pest_code(pest_type),
        severity=severity,
        province=province,
        municipality=municipality,
        crop_growth_stage=crop_growth_stage,
        date_spotted=date_spotted,
        notes=notes,
        area_affected=area_affected,
        latitude=latitude,
        longitude=longitude,
        estimated_value=estimated_value,
        photo_path=photo_path,
        ai_pest_detected=ai_pest_detected,
        ai_confidence=ai_confidence,
        ai_suggested_count=ai_suggested_count,
        ai_suggested_coverage_pct=ai_suggested_coverage_pct,
        ai_suggested_damage_pct=ai_suggested_damage_pct,
    )

    reports_store.create_report(record)

    return ReportResponse(id=record.id, submitted_at=record.submitted_at)


@router.patch("/{report_id}", response_model=ReportRecord)
def update_report_status(
    report_id: str, payload: ReportStatusUpdate, lgu: TokenPayload = Depends(require_lgu)
) -> ReportRecord:
    """LGU review action from admin-web: mark a farmer's sighting verified or
    rejected. Only "verified" reports feed Gap Analysis (app/decision/report_anchor.py)
    and the periodic retrain (ml/bilstm/ingest_reports.py) — a pending or
    rejected report never influences either.

    LGU-only, scoped to the technician's own municipality — same pattern as
    delete_report below. verified_by is taken from the authenticated token,
    never the request body: a client-supplied verified_by would let anyone
    forge who verified a report, which matters here since verification is
    what ultimately feeds model retraining.
    """
    report = reports_store.get_report(report_id)
    if report is None or report.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    account = find_lgu_user(lgu.username)
    if account is None or account.municipality.lower() != report.municipality.lower():
        raise HTTPException(status_code=403, detail="You can only review reports from your own municipality")

    updated = reports_store.update_report_status(report_id, payload.status, lgu.username, payload.verified_value)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated


@router.get("/{report_id}/gap-analysis", response_model=GapAnalysisResponse)
def get_report_gap_analysis(report_id: str) -> GapAnalysisResponse:
    """Per-report 'Analyze Gap' button on admin-web's Farmer Reports tab:
    for ONE verified report, the 14-day forecast starting on the report's
    own date, from the deployed model, two ways — without any verified
    report as input (historical) and with THIS report as its verified-
    observation input (report-based) — alongside the field value the
    technologist confirmed, plus a plain-language implication
    (app/decision/gap_implication.py).

    "Report-based" mirrors exactly what the live forecast does once a report
    is verified (app/routers/inference.py's _run_forecast / _build_trajectory:
    the observation is looked up once and fed to every point as an input).
    It replaced a post-hoc fading shift on 2026-10-21, after that shift had
    already been removed from the live forecast — the gap analysis was
    otherwise showing a mechanism the system no longer uses.

    The historical line is unchanged by that switch, which keeps
    ml/validity_test.py's field-validity check (historical day 0 vs. the
    verified value) meaning what it did. Read-only.
    """
    report = reports_store.get_report(report_id)
    if report is None or report.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    pest_code = report.pest_code or derive_pest_code(report.pest_type)
    if pest_code not in PEST_PARAMS:
        raise HTTPException(
            status_code=400,
            detail=f"Report '{report_id}' isn't for a tracked pest (BPH/RSB) — nothing to analyze.",
        )

    growth_stage = report.crop_growth_stage if report.crop_growth_stage in GROWTH_STAGE_BUCKETS else "Tillering"
    growth_stage_bucket = GROWTH_STAGE_BUCKETS[growth_stage]

    anchor = anchor_from_report(report, growth_stage_bucket)
    if anchor is None:
        return GapAnalysisResponse(
            status="report_not_verified",
            report_id=report_id,
            municipality=report.municipality,
            pest=pest_code,
            days=[],
            implication="This report hasn't been verified yet, or has no usable count/severity — verify it first.",
            message="Report is not usable as a gap-analysis anchor.",
        )

    coordinates = municipality_coordinates(report.municipality)
    if coordinates is None:
        raise HTTPException(
            status_code=404,
            detail=f"No coordinates on file for municipality '{report.municipality}'.",
        )
    latitude, longitude = coordinates

    window_days = PEST_PARAMS[pest_code].crf_window_days
    report_date = anchor.anchor_date

    # A full 14-day trajectory, starting on the report's own date, the same
    # length the live forecast chart shows.
    DISPLAY_DAYS = 14

    # The window for the LAST day we'll show (report_date + DISPLAY_DAYS - 1)
    # ends FORECAST_HORIZON_DAYS before that target, and itself needs
    # window_days of history before it starts — see _window_for_target.
    fetch_start = report_date - timedelta(days=FORECAST_HORIZON_DAYS + window_days)
    fetch_end = report_date + timedelta(days=DISPLAY_DAYS - 1)
    daily_weather = fetch_daily_weather_range(latitude, longitude, fetch_start, fetch_end)
    weather_by_date = {day["date"]: day for day in daily_weather}

    # The report enters the model the same way the live forecast feeds it:
    # (value, days since the report, has-report). Every displayed day uses
    # age 0 — the forecast as it would look right after this report was
    # verified — matching _build_trajectory, which looks the observation up
    # once and reuses it for every point rather than re-aging it per day.
    report_input = (float(anchor.verified_value), 0.0, 1.0)
    report_is_model_input = bilstm_forecaster.accepts_observation(pest_code)

    days: list[GapAnalysisDay] = []
    unit: str | None = None

    for offset in range(DISPLAY_DAYS):
        target_date = report_date + timedelta(days=offset)
        window = _window_for_target(pest_code, target_date, growth_stage, weather_by_date)

        historical_value: float | None = None
        historical_risk_level = None
        report_based_value: float | None = None
        report_based_risk_level = None

        if window is not None:
            historical = bilstm_forecaster.predict(pest_code, window)
            if historical is None:
                return GapAnalysisResponse(
                    status="model_not_loaded",
                    report_id=report_id,
                    municipality=report.municipality,
                    pest=pest_code,
                    days=[],
                    implication="",
                    message=f"BiLSTM model for {pest_code} not loaded yet.",
                )
            with_report = bilstm_forecaster.predict(pest_code, window, report_input)
            unit = historical.unit
            historical_value = historical.predicted_value
            historical_risk_level = derive_risk_level(pest_code, growth_stage_bucket, historical_value)
            report_based_value = with_report.predicted_value
            report_based_risk_level = derive_risk_level(pest_code, growth_stage_bucket, report_based_value)

        days.append(
            GapAnalysisDay(
                date=target_date.isoformat(),
                historical_value=historical_value,
                historical_risk_level=historical_risk_level,
                report_based_value=report_based_value,
                report_based_risk_level=report_based_risk_level,
            )
        )

    verified_risk_level = derive_risk_level(pest_code, growth_stage_bucket, anchor.verified_value)
    implication = describe_gap(days, pest_code, verified_risk_level, report_is_model_input)

    return GapAnalysisResponse(
        status="ok",
        report_id=report_id,
        municipality=report.municipality,
        pest=pest_code,
        unit=unit,
        days=days,
        verified_value=float(anchor.verified_value),
        verified_risk_level=verified_risk_level,
        report_is_model_input=report_is_model_input,
        implication=implication,
        message="Gap analysis successful",
    )


@router.get("/deleted", response_model=list[ReportRecord])
def list_deleted_reports(lgu: TokenPayload = Depends(require_lgu)) -> list[ReportRecord]:
    """Audit trail for admin-web's "Deleted Reports" tab: the technician's
    own municipality only, and only with an LGU login (the public feed
    endpoint above never returns deleted reports)."""
    account = find_lgu_user(lgu.username)
    if account is None:
        raise HTTPException(status_code=403, detail="LGU account not found")
    return reports_store.list_deleted_reports(account.municipality)


@router.delete("/{report_id}", response_model=ReportRecord)
def delete_report(report_id: str, lgu: TokenPayload = Depends(require_lgu)) -> ReportRecord:
    """LGU-only soft delete of a sighting (any status), limited to the
    technician's own municipality. The report is kept as an audit trail —
    who deleted it and when — but immediately stops feeding the forecast
    (app/decision/report_anchor.py) and the farmers' alerts feed."""
    report = reports_store.get_report(report_id)
    if report is None or report.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    account = find_lgu_user(lgu.username)
    if account is None or account.municipality.lower() != report.municipality.lower():
        raise HTTPException(status_code=403, detail="You can only delete reports from your own municipality")

    deleted = reports_store.delete_report(report_id, deleted_by=lgu.username)
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return deleted

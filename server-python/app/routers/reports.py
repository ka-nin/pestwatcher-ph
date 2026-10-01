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
from app.decision.report_anchor import anchor_from_report, shifted, weight
from app.dependencies import require_lgu
from app.models.bilstm_model import bilstm_forecaster
from app.models.resnet_model import resnet_classifier
from app.rate_limit import RateLimitExceeded, RateLimiter
from app.routers.inference import _window_for_target
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
    )

    reports_store.create_report(record)

    return ReportResponse(id=record.id, submitted_at=record.submitted_at)


@router.patch("/{report_id}", response_model=ReportRecord)
def update_report_status(report_id: str, payload: ReportStatusUpdate) -> ReportRecord:
    """LGU review action from admin-web: mark a farmer's sighting verified or
    rejected. Only "verified" reports feed into the forecast adjustment in
    app/decision/report_anchor.py — a pending or rejected report never
    influences what a farmer sees on their dashboard."""
    updated = reports_store.update_report_status(
        report_id, payload.status, payload.verified_by, payload.verified_value
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated


@router.get("/{report_id}/gap-analysis", response_model=GapAnalysisResponse)
def get_report_gap_analysis(report_id: str) -> GapAnalysisResponse:
    """Per-report 'Analyze Gap' button on admin-web's Farmer Reports tab:
    for ONE verified report, shows the 14-day forecast starting on the
    report's own date two ways — the plain weather-only model (historical)
    and what the forecast would look like if this report were allowed to
    anchor it (report-based, via app/decision/report_anchor.py's fading
    shift) — plus a plain-language implication (app/decision/gap_implication.py).

    Read-only, same as every other gap-analysis path: neither trajectory
    here is what a farmer or technician sees as a live prediction (see
    app/routers/inference.py's _run_forecast docstring for why verified
    reports no longer shift that).
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

    # A full 14-day trajectory, starting on the report's own date — this is
    # a DISPLAY length, deliberately independent of ANCHOR_DAYS (13), which
    # is the separate fade-window constant report_anchor.py's weight() uses
    # internally. The two happen to be close, but conflating them previously
    # cut this endpoint's trajectory one day short (13 days shown, not 14) —
    # weight() naturally reaches 0% once a displayed day falls outside its
    # own fade window, so DISPLAY_DAYS running one day longer than
    # ANCHOR_DAYS is expected, not a bug: it just means the report-based
    # line has already fully settled back to the historical one by then.
    DISPLAY_DAYS = 14

    # The window for the LAST day we'll show (report_date + DISPLAY_DAYS - 1)
    # ends FORECAST_HORIZON_DAYS before that target, and itself needs
    # window_days of history before it starts — see _window_for_target.
    fetch_start = report_date - timedelta(days=FORECAST_HORIZON_DAYS + window_days)
    fetch_end = report_date + timedelta(days=DISPLAY_DAYS - 1)
    daily_weather = fetch_daily_weather_range(latitude, longitude, fetch_start, fetch_end)
    weather_by_date = {day["date"]: day for day in daily_weather}

    # The "gap" (app/decision/report_anchor.py) is defined relative to the
    # model's OWN baseline for the report's day specifically — not
    # recomputed per day, which would be a different quantity. If that
    # baseline can't be computed (missing weather history that far back),
    # no day in this trajectory can be report-anchored either.
    baseline_window = _window_for_target(pest_code, report_date, growth_stage, weather_by_date)
    baseline_result = bilstm_forecaster.predict(pest_code, baseline_window) if baseline_window is not None else None
    if baseline_window is not None and baseline_result is None:
        return GapAnalysisResponse(
            status="model_not_loaded",
            report_id=report_id,
            municipality=report.municipality,
            pest=pest_code,
            days=[],
            implication="",
            message=f"BiLSTM model for {pest_code} not loaded yet.",
        )
    gap = anchor.verified_value - baseline_result.predicted_value if baseline_result is not None else None

    days: list[GapAnalysisDay] = []
    unit: str | None = None

    for offset in range(DISPLAY_DAYS):
        target_date = report_date + timedelta(days=offset)
        window = _window_for_target(pest_code, target_date, growth_stage, weather_by_date)
        day_weight = weight(anchor, target_date)

        historical_value: float | None = None
        historical_risk_level = None
        report_based_value: float | None = None
        report_based_risk_level = None

        if window is not None:
            result = bilstm_forecaster.predict(pest_code, window)
            if result is not None:
                unit = result.unit
                historical_value = result.predicted_value
                historical_risk_level = derive_risk_level(pest_code, growth_stage_bucket, historical_value)

                if gap is not None:
                    report_based_value = shifted(historical_value, gap, day_weight)
                    report_based_risk_level = derive_risk_level(pest_code, growth_stage_bucket, report_based_value)

        days.append(
            GapAnalysisDay(
                date=target_date.isoformat(),
                historical_value=historical_value,
                historical_risk_level=historical_risk_level,
                report_based_value=report_based_value,
                report_based_risk_level=report_based_risk_level,
                report_weight=day_weight,
            )
        )

    implication = describe_gap(days, pest_code)

    return GapAnalysisResponse(
        status="ok",
        report_id=report_id,
        municipality=report.municipality,
        pest=pest_code,
        unit=unit,
        days=days,
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

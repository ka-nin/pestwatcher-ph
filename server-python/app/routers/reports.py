import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config import get_settings
from app.data import reports_store
from app.data.lgu_users import find_lgu_user
from app.decision.pest_matching import derive_pest_code
from app.dependencies import require_lgu
from app.models.resnet_model import resnet_classifier
from app.rate_limit import RateLimitExceeded, RateLimiter
from app.security import TokenPayload
from app.schemas.reports import ReportRecord, ReportResponse, ReportStatusUpdate

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

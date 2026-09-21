import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.data import reports_store
from app.models.resnet_model import resnet_classifier
from app.schemas.reports import ReportRecord, ReportResponse, ReportStatusUpdate

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Same allowlist as /api/inference/image (app/routers/inference.py) — kept
# duplicated rather than imported to avoid coupling the two routers over
# what's otherwise an unrelated constant.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


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

        # Best-effort: predict_best() returns None until at least one
        # pest's weights are loaded (app/models/resnet_model.py) — a report
        # with a photo but no AI read is a normal, expected state, same as
        # /api/inference/image's "model_not_loaded". Runs every loaded
        # pest's classifier and keeps whichever fires strongest, since a
        # report photo isn't necessarily of the pest the farmer picked.
        best = resnet_classifier.predict_best(upload_dir / photo_path)
        if best is not None:
            ai_pest_detected = best[1].label
            ai_confidence = best[1].confidence

    record = ReportRecord(
        id=uuid.uuid4().hex,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        username=username,
        pest_type=pest_type,
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
    app/decision/report_signal.py — a pending or rejected report never
    influences what a farmer sees on their dashboard."""
    updated = reports_store.update_report_status(
        report_id, payload.status, payload.verified_by, payload.verified_value
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.models.resnet_model import resnet_classifier
from app.schemas.reports import ReportRecord, ReportResponse, ReportStatusUpdate

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Same allowlist as /api/inference/image (app/routers/inference.py) — kept
# duplicated rather than imported to avoid coupling the two routers over
# what's otherwise an unrelated constant.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _reports_file() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir).parent / "reports.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _with_photo_url(record: dict) -> dict:
    """Reports are stored with only a photo_path (on-disk filename); the
    /uploads-mounted URL (see app/main.py) is derived at read time so
    nothing about the static mount ever gets baked into the stored file."""
    if record.get("photo_path"):
        record = {**record, "photo_url": f"/uploads/{record['photo_path']}"}
    return record


@router.get("", response_model=list[ReportRecord])
def list_reports(province: str | None = None, municipality: str | None = None) -> list[ReportRecord]:
    """Farmer-submitted sightings, most recent first.

    `province` backs the mobile app's broader "regional alerts" feed
    (neighboring municipalities included); `municipality` is what
    admin-web's tenant-scoped Reports tab uses — an LGU technician should
    only ever see sightings from their own municipality, not the whole
    province. Both are optional and combinable.
    """
    path = _reports_file()
    if not path.exists():
        return []
    records = [_with_photo_url(r) for r in json.loads(path.read_text(encoding="utf-8"))]
    if province:
        records = [r for r in records if r.get("province", "").lower() == province.lower()]
    if municipality:
        records = [r for r in records if r.get("municipality", "").lower() == municipality.lower()]
    return sorted([ReportRecord(**r) for r in records], key=lambda r: r.submitted_at, reverse=True)


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
    file: UploadFile | None = File(None),
) -> ReportResponse:
    """Farmer-submitted pest sighting — multipart/form-data so an optional
    photo can ride along with it (the mobile app's primary "report with
    photo" path) rather than requiring a separate upload call. A manual,
    photo-less report (the fallback path) is the same endpoint with `file`
    omitted. Appends to a flat JSON file — replace with a real database
    table once persistence is wired up (same placeholder approach as
    app/data/farmer_users.py).
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
        photo_path=photo_path,
        ai_pest_detected=ai_pest_detected,
        ai_confidence=ai_confidence,
    )

    path = _reports_file()
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    records.append(record.model_dump(exclude={"photo_url"}))
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    return ReportResponse(id=record.id, submitted_at=record.submitted_at)


@router.patch("/{report_id}", response_model=ReportRecord)
def update_report_status(report_id: str, payload: ReportStatusUpdate) -> ReportRecord:
    """LGU review action from admin-web: mark a farmer's sighting verified or
    rejected. Only "verified" reports feed into the forecast adjustment in
    app/decision/report_signal.py — a pending or rejected report never
    influences what a farmer sees on their dashboard."""
    path = _reports_file()
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    for r in records:
        if r["id"] == report_id:
            r["status"] = payload.status
            r["verified_by"] = payload.verified_by
            r["verified_at"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            return ReportRecord(**_with_photo_url(r))

    raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

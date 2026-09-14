import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.reports import ReportRecord, ReportRequest, ReportResponse

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _reports_file() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir).parent / "reports.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@router.post("", response_model=ReportResponse)
def submit_report(payload: ReportRequest) -> ReportResponse:
    """Farmer-submitted manual pest sighting report. Appends to a flat JSON
    file — replace with a real database table once persistence is wired up
    (same placeholder approach as app/data/farmer_users.py)."""
    record = ReportRecord(
        id=uuid.uuid4().hex,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        **payload.model_dump(),
    )

    path = _reports_file()
    records = json.loads(path.read_text()) if path.exists() else []
    records.append(record.model_dump())
    path.write_text(json.dumps(records, indent=2))

    return ReportResponse(id=record.id, submitted_at=record.submitted_at)

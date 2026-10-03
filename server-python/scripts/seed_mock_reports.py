"""Inserts mock farmer reports across Nueva Ecija municipalities, for demos
and simulation only. Idempotent: every row has a fixed "mock-" id, so
re-running skips ones that already exist.

Run from server-python/ with the venv active and the database up:
    python -m scripts.seed_mock_reports            # insert
    python -m scripts.seed_mock_reports --remove   # delete all mock rows

Dates are relative to today so the reports stay "recent" for the forecast
anchor (app/decision/report_anchor.py).
"""

import sys
from datetime import datetime, timedelta, timezone

from app.db import init_db, session_scope
from app.data import reports_store
from app.db_models import ReportDB
from app.decision.pest_matching import derive_pest_code
from app.schemas.reports import ReportRecord

PROVINCE = "Nueva Ecija"

BPH = "Brown Planthopper (Kayumangging Hanip)"
RSB = "Rice Stem Borer (Aksip)"

# (id suffix, municipality, lat, lon, pest, severity, stage, days ago, est. value, status, notes)
_MOCKS = [
    ("01", "Science City of Muñoz", 15.7210, 120.9130, BPH, "high", "Tillering", 1, 18.0, "verified",
     "Maraming hanip sa ibabang bahagi ng palay, nagsisimula na ang hopperburn."),
    ("02", "San Jose City", 15.7889, 120.9856, RSB, "medium", "Booting", 2, 8.0, "pending",
     "Dead hearts sa ilang tanim malapit sa irrigation canal."),
    ("03", "Cabanatuan City", 15.4869, 120.9675, BPH, "medium", "Tillering", 3, 9.0, "pending",
     "Around 9 hoppers per hill on 5 sampled hills."),
    ("04", "Guimba", 15.6606, 120.7681, RSB, "high", "Flowering", 1, 15.0, "verified",
     "Whiteheads visible across a large section of the paddy."),
    ("05", "Talavera", 15.5878, 120.9225, BPH, "low", "Seedling", 4, 3.0, "pending",
     "Few hoppers only, monitoring."),
    ("06", "Gapan City", 15.3075, 120.9464, BPH, "high", "Booting", 2, 22.0, "pending",
     "Yellowing patches spreading from the field edge."),
    ("07", "Palayan City", 15.5431, 121.0797, RSB, "low", "Tillering", 5, 2.0, "pending",
     "Isolated dead hearts, wala pang malawakang damage."),
    ("08", "Santa Rosa", 15.4222, 120.9403, BPH, "medium", "Flowering", 3, 11.0, "rejected",
     "Photo unclear, could not confirm the pest."),
]


def _build(row) -> ReportRecord:
    suffix, municipality, lat, lon, pest, severity, stage, days_ago, value, status, notes = row
    now = datetime.now(timezone.utc)
    spotted = now - timedelta(days=days_ago)
    record = ReportRecord(
        id=f"mock-{suffix}",
        username="mock_farmer",
        pest_type=pest,
        pest_code=derive_pest_code(pest),
        severity=severity,
        province=PROVINCE,
        municipality=municipality,
        crop_growth_stage=stage,
        date_spotted=spotted.date().isoformat(),
        notes=notes,
        latitude=lat,
        longitude=lon,
        estimated_value=value,
        submitted_at=spotted.isoformat(),
        status=status,
    )
    if status != "pending":
        record.verified_by = "mock_lgu"
        record.verified_at = (spotted + timedelta(hours=6)).isoformat()
        record.verified_value = value if status == "verified" else None
    return record


def insert() -> None:
    added = 0
    for row in _MOCKS:
        record = _build(row)
        with session_scope() as db:
            if db.get(ReportDB, record.id) is not None:
                continue
        reports_store.create_report(record)
        added += 1
    print(f"Inserted {added} mock report(s); {len(_MOCKS) - added} already existed.")


def remove() -> None:
    with session_scope() as db:
        n = db.query(ReportDB).filter(ReportDB.id.like("mock-%")).delete(synchronize_session=False)
    print(f"Removed {n} mock report(s).")


if __name__ == "__main__":
    init_db()
    remove() if "--remove" in sys.argv else insert()

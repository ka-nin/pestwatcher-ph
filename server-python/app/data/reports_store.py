"""Farmer-submitted sighting reports, backed by the `reports` Postgres table
(app/db_models.py:ReportDB). migrate_from_json_if_empty() imports whatever
was in the old flat reports.json file on first startup, so existing local
dev data isn't lost by this migration.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from app.db import session_scope
from app.db_models import ReportDB
from app.decision.pest_matching import derive_pest_code
from app.schemas.reports import ReportRecord


def _to_schema(row: ReportDB) -> ReportRecord:
    data = {
        "id": row.id,
        "username": row.username,
        "pest_type": row.pest_type,
        "pest_code": row.pest_code,
        "severity": row.severity,
        "province": row.province,
        "municipality": row.municipality,
        "crop_growth_stage": row.crop_growth_stage,
        "date_spotted": row.date_spotted,
        "notes": row.notes,
        "area_affected": row.area_affected,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "estimated_value": row.estimated_value,
        "submitted_at": row.submitted_at,
        "status": row.status,
        "verified_by": row.verified_by,
        "verified_at": row.verified_at,
        "verified_value": row.verified_value,
        "photo_path": row.photo_path,
        "ai_pest_detected": row.ai_pest_detected,
        "ai_confidence": row.ai_confidence,
    }
    if data["photo_path"]:
        data["photo_url"] = f"/uploads/{data['photo_path']}"
    return ReportRecord(**data)


def migrate_from_json_if_empty(json_path: Path) -> None:
    with session_scope() as db:
        if db.query(ReportDB).first() is not None:
            return
        if not json_path.exists():
            return
        records = json.loads(json_path.read_text(encoding="utf-8"))
        for r in records:
            db.add(
                ReportDB(
                    id=r["id"],
                    username=r.get("username", "Anonymous Farmer"),
                    pest_type=r["pest_type"],
                    pest_code=r.get("pest_code") or derive_pest_code(r["pest_type"]),
                    severity=r["severity"],
                    province=r["province"],
                    municipality=r["municipality"],
                    crop_growth_stage=r.get("crop_growth_stage", "Tillering"),
                    date_spotted=r["date_spotted"],
                    notes=r.get("notes", ""),
                    area_affected=r.get("area_affected"),
                    latitude=r.get("latitude"),
                    longitude=r.get("longitude"),
                    estimated_value=r.get("estimated_value"),
                    submitted_at=r["submitted_at"],
                    status=r.get("status", "pending"),
                    verified_by=r.get("verified_by"),
                    verified_at=r.get("verified_at"),
                    verified_value=r.get("verified_value"),
                    photo_path=r.get("photo_path"),
                    ai_pest_detected=r.get("ai_pest_detected"),
                    ai_confidence=r.get("ai_confidence"),
                )
            )


def backfill_pest_codes() -> None:
    """One-time-per-row fix-up for reports written before the pest_code
    column existed (it's nullable, so create_all() won't retroactively
    populate it on an existing table — see app/db.py's docstring on this
    project having no migration framework). Safe to call on every startup:
    only touches rows where pest_code is still null, and is a no-op once
    they're all set."""
    with session_scope() as db:
        rows = db.query(ReportDB).filter(ReportDB.pest_code.is_(None)).all()
        for row in rows:
            code = derive_pest_code(row.pest_type)
            if code is not None:
                row.pest_code = code


def list_reports(province: str | None = None, municipality: str | None = None) -> list[ReportRecord]:
    with session_scope() as db:
        query = db.query(ReportDB)
        if province:
            query = query.filter(func.lower(ReportDB.province) == province.lower())
        if municipality:
            query = query.filter(func.lower(ReportDB.municipality) == municipality.lower())
        rows = query.order_by(ReportDB.submitted_at.desc()).all()
        return [_to_schema(r) for r in rows]


def list_verified_reports(municipality: str) -> list[ReportRecord]:
    """Used by app/decision/report_signal.py to gather ground-truth signal
    for one municipality — recency and pest matching are filtered by the
    caller, not here."""
    with session_scope() as db:
        rows = (
            db.query(ReportDB)
            .filter(ReportDB.status == "verified", ReportDB.municipality == municipality)
            .all()
        )
        return [_to_schema(r) for r in rows]


def count_recent_similar_reports(username: str, municipality: str, pest_type: str, since_iso: str) -> int:
    """Used by app/routers/reports.py to reject an accidental double-submit
    or a spammed repeat of the same sighting — same farmer, municipality,
    and pest, within a short trailing window. `submitted_at` is stored as
    an ISO 8601 string with a fixed UTC offset (see create_report), which
    sorts lexicographically the same as chronologically, so a plain string
    comparison works without parsing every row back into a datetime.
    """
    with session_scope() as db:
        return (
            db.query(ReportDB)
            .filter(
                ReportDB.username == username,
                ReportDB.municipality == municipality,
                ReportDB.pest_type == pest_type,
                ReportDB.submitted_at >= since_iso,
            )
            .count()
        )


def create_report(record: ReportRecord) -> None:
    with session_scope() as db:
        data = record.model_dump(exclude={"photo_url"})
        db.add(ReportDB(**data))


def update_report_status(
    report_id: str,
    status: str,
    verified_by: str,
    verified_value: float | None = None,
) -> ReportRecord | None:
    with session_scope() as db:
        row = db.get(ReportDB, report_id)
        if row is None:
            return None
        row.status = status
        row.verified_by = verified_by
        row.verified_at = datetime.now(timezone.utc).isoformat()
        if status == "verified":
            row.verified_value = verified_value if verified_value is not None else row.estimated_value
        else:
            row.verified_value = None
        db.flush()
        return _to_schema(row)

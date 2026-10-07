"""SMS outbox persistence, backed by the `sms_messages` Postgres table
(app/db_models.py:SmsMessageDB).

Rows are written queued *before* the send is attempted and updated after, so
an attempt is never lost to a crash or a timeout halfway through a batch.
"""

from datetime import datetime, timezone

from app.db import session_scope
from app.db_models import SmsMessageDB
from app.schemas.sms import SmsMessageRecord


def _to_schema(row: SmsMessageDB) -> SmsMessageRecord:
    return SmsMessageRecord(
        id=row.id,
        batch_id=row.batch_id,
        recipient_phone=row.recipient_phone,
        recipient_username=row.recipient_username,
        recipient_name=row.recipient_name,
        body=row.body,
        municipality=row.municipality,
        sent_by=row.sent_by,
        status=row.status,
        provider=row.provider,
        provider_message_id=row.provider_message_id,
        error=row.error,
        created_at=row.created_at,
        sent_at=row.sent_at,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def queue_message(
    *,
    message_id: str,
    batch_id: str,
    recipient_phone: str,
    recipient_username: str | None,
    recipient_name: str | None,
    body: str,
    municipality: str,
    sent_by: str,
    provider: str,
) -> None:
    with session_scope() as db:
        db.add(
            SmsMessageDB(
                id=message_id,
                batch_id=batch_id,
                recipient_phone=recipient_phone,
                recipient_username=recipient_username,
                recipient_name=recipient_name,
                body=body,
                municipality=municipality,
                sent_by=sent_by,
                status="queued",
                provider=provider,
                created_at=_now(),
            )
        )


def mark_result(
    message_id: str, *, ok: bool, provider_message_id: str | None, error: str | None
) -> SmsMessageRecord | None:
    with session_scope() as db:
        row = db.get(SmsMessageDB, message_id)
        if row is None:
            return None
        row.status = "sent" if ok else "failed"
        row.provider_message_id = provider_message_id
        row.error = error
        row.sent_at = _now() if ok else None
        db.flush()
        return _to_schema(row)


def list_messages(municipality: str | None = None, limit: int = 200) -> list[SmsMessageRecord]:
    """Newest first. Scoped by municipality so a technologist sees their own
    outbox only, the same rule the reports endpoints use."""
    with session_scope() as db:
        query = db.query(SmsMessageDB)
        if municipality:
            query = query.filter(SmsMessageDB.municipality.ilike(municipality))
        rows = query.order_by(SmsMessageDB.created_at.desc()).limit(limit).all()
        return [_to_schema(row) for row in rows]

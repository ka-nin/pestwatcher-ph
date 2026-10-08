"""B2C farmer accounts for the mobile app, backed by the `farmer_users`
Postgres table (app/db_models.py:FarmerUserDB). seed_if_empty() inserts the
one demo account on first startup, same as before this migration.

Passwords are bcrypt hashes (see app/security.py). Plaintext dev credential:
    farmer_demo / RicePest!Demo2026
"""

from app.db import session_scope
from app.db_models import FarmerUserDB
from app.schemas.auth import FarmerUser

_SEED_USERS = [
    FarmerUser(
        username="farmer_demo",
        password_hash="$2b$12$WDtaPhz4iJdo06tmQ1sXyOhRJ3zBLxQ5Y4vhdG.SVZVBIDTJqpg/S",
        full_name="Demo Farmer",
        municipality="Science City of Muñoz",
        province="Nueva Ecija",
        latitude=15.7167,
        longitude=120.9167,
    ),
]


def _to_schema(row: FarmerUserDB) -> FarmerUser:
    return FarmerUser(
        username=row.username,
        password_hash=row.password_hash,
        full_name=row.full_name,
        province=row.province,
        municipality=row.municipality,
        latitude=row.latitude,
        longitude=row.longitude,
        phone=row.phone,
    )


def seed_if_empty() -> None:
    with session_scope() as db:
        if db.query(FarmerUserDB).first() is not None:
            return
        for user in _SEED_USERS:
            db.add(FarmerUserDB(**user.model_dump()))


def find_farmer_user(username: str) -> FarmerUser | None:
    with session_scope() as db:
        row = db.get(FarmerUserDB, username)
        return _to_schema(row) if row else None


def list_farmers(municipality: str | None = None) -> list[FarmerUser]:
    """Farmer accounts, optionally scoped to one municipality. Used by the SMS
    compose screen, which only ever offers a technologist their own town."""
    with session_scope() as db:
        query = db.query(FarmerUserDB)
        if municipality:
            query = query.filter(FarmerUserDB.municipality.ilike(municipality))
        rows = query.order_by(FarmerUserDB.full_name).all()
        return [_to_schema(row) for row in rows]


def set_phone(username: str, phone: str | None) -> FarmerUser | None:
    with session_scope() as db:
        row = db.get(FarmerUserDB, username)
        if row is None:
            return None
        row.phone = phone
        db.flush()
        return _to_schema(row)

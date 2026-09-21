"""LGU municipal technician accounts, backed by the `lgu_users` Postgres
table (app/db_models.py:LguUserDB). On first startup with an empty table,
seed_if_empty() inserts the same four accounts that used to be hardcoded
here, so nothing changes for local dev — see credentials.txt for their
plaintext passwords.
"""

from app.db import session_scope
from app.db_models import LguUserDB
from app.schemas.auth import LguUser

_SEED_USERS = [
    LguUser(
        username="munoz_tech_01",
        password_hash="$2b$12$x/eVjk6bUEA7ofwMP3PR9euDDNQiHRo2EtRrUQsPBsUdo90I4pHt6",
        role_level="LGU_Tech",
        province="Nueva Ecija",
        municipality="Science City of Muñoz",
        latitude=15.7167,
        longitude=120.9167,
    ),
    LguUser(
        username="concepcion_tech",
        password_hash="$2b$12$eOctUfA4c/trF5o0mcp8DeRMxUx3KTvp1wsAIgycmak2eCoIqB2dq",
        role_level="LGU_Tech",
        province="Tarlac",
        municipality="Concepcion",
        latitude=15.3167,
        longitude=120.6333,
    ),
    LguUser(
        username="sanmiguel_tech",
        password_hash="$2b$12$yppxuekDj/t.11vZSQoLDeII8ldHYFflgbRHiR3RB3cEQSw9AipD2",
        role_level="LGU_Tech",
        province="Bulacan",
        municipality="San Miguel",
        latitude=15.15,
        longitude=120.9667,
    ),
    LguUser(
        username="arayat_tech_01",
        password_hash="$2b$12$FOIFBU6Kdo/yrW8JexuQfOMVqSJu1yY7s4haAps2PZRd1EIYoF9La",
        role_level="LGU_Tech",
        province="Pampanga",
        municipality="Arayat",
        latitude=15.4167,
        longitude=120.7333,
    ),
]


def _to_schema(row: LguUserDB) -> LguUser:
    return LguUser(
        username=row.username,
        password_hash=row.password_hash,
        role_level=row.role_level,
        province=row.province,
        municipality=row.municipality,
        latitude=row.latitude,
        longitude=row.longitude,
        is_active=row.is_active,
    )


def seed_if_empty() -> None:
    with session_scope() as db:
        if db.query(LguUserDB).first() is not None:
            return
        for user in _SEED_USERS:
            db.add(LguUserDB(**user.model_dump()))


def list_lgu_users() -> list[LguUser]:
    with session_scope() as db:
        return [_to_schema(r) for r in db.query(LguUserDB).order_by(LguUserDB.username).all()]


def find_lgu_user(username: str) -> LguUser | None:
    with session_scope() as db:
        row = db.get(LguUserDB, username)
        return _to_schema(row) if row else None


def municipality_coordinates(municipality: str) -> tuple[float, float] | None:
    """Looks up (latitude, longitude) for a municipality from the LGU
    accounts table, so live weather fetches don't need their own separate
    coordinate table."""
    with session_scope() as db:
        row = db.query(LguUserDB).filter(LguUserDB.municipality == municipality).first()
        return (row.latitude, row.longitude) if row else None


def add_lgu_user(user: LguUser) -> None:
    with session_scope() as db:
        if db.get(LguUserDB, user.username) is not None:
            raise ValueError(f"LGU user '{user.username}' already exists")
        db.add(LguUserDB(**user.model_dump()))


def update_lgu_user(
    username: str,
    *,
    password_hash: str | None = None,
    role_level: str | None = None,
    province: str | None = None,
    municipality: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    is_active: bool | None = None,
) -> LguUser | None:
    with session_scope() as db:
        row = db.get(LguUserDB, username)
        if row is None:
            return None
        if password_hash is not None:
            row.password_hash = password_hash
        if role_level is not None:
            row.role_level = role_level
        if province is not None:
            row.province = province
        if municipality is not None:
            row.municipality = municipality
        if latitude is not None:
            row.latitude = latitude
        if longitude is not None:
            row.longitude = longitude
        if is_active is not None:
            row.is_active = is_active
        db.flush()
        return _to_schema(row)


def delete_lgu_user(username: str) -> bool:
    with session_scope() as db:
        row = db.get(LguUserDB, username)
        if row is None:
            return False
        db.delete(row)
        return True

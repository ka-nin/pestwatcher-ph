"""Canonical municipality/coordinate registry, backed by the
`municipalities` Postgres table (app/db_models.py:MunicipalityDB).

Previously the only place municipality coordinates lived was the lgu_users
table (see lgu_users.municipality_coordinates(), still present for backward
compatibility but no longer used by app/routers/inference.py or
app/routers/locations.py). That meant a municipality was only visible to
weather lookups and the mobile app's picker if it happened to already have
an LGU account — this table decouples the two, and is grown automatically
by upsert_municipality() whenever a superadmin adds or edits an LGU account
for a municipality not seen before (see app/routers/admin.py).
"""

from app.db import session_scope
from app.db_models import MunicipalityDB
from app.schemas.locations import MunicipalityOption

# Same four towns lgu_users.py and farmer_users.py already seed accounts
# for — kept as a separate literal list rather than importing those seed
# lists, since seeding order at startup isn't guaranteed and this table
# should not depend on account data existing first.
_SEED_MUNICIPALITIES = [
    MunicipalityOption(municipality="Science City of Muñoz", province="Nueva Ecija",
                        latitude=15.7167, longitude=120.9167),
    MunicipalityOption(municipality="Concepcion", province="Tarlac",
                        latitude=15.3167, longitude=120.6333),
    MunicipalityOption(municipality="San Miguel", province="Bulacan",
                        latitude=15.15, longitude=120.9667),
    MunicipalityOption(municipality="Arayat", province="Pampanga",
                        latitude=15.4167, longitude=120.7333),
]


def _to_schema(row: MunicipalityDB) -> MunicipalityOption:
    return MunicipalityOption(
        municipality=row.municipality,
        province=row.province,
        latitude=row.latitude,
        longitude=row.longitude,
    )


def seed_if_empty() -> None:
    with session_scope() as db:
        if db.query(MunicipalityDB).first() is not None:
            return
        for m in _SEED_MUNICIPALITIES:
            db.add(MunicipalityDB(**m.model_dump()))


def list_municipalities() -> list[MunicipalityOption]:
    with session_scope() as db:
        rows = db.query(MunicipalityDB).order_by(MunicipalityDB.municipality).all()
        return [_to_schema(r) for r in rows]


def municipality_coordinates(municipality: str) -> tuple[float, float] | None:
    with session_scope() as db:
        row = db.get(MunicipalityDB, municipality)
        return (row.latitude, row.longitude) if row else None


def upsert_municipality(municipality: str, province: str, latitude: float, longitude: float) -> None:
    """Inserts the municipality if new, or refreshes its province/coordinates
    if they changed. Called whenever an LGU account is created or edited
    with a municipality (app/routers/admin.py) so the registry stays
    current without requiring a separate superadmin workflow."""
    with session_scope() as db:
        row = db.get(MunicipalityDB, municipality)
        if row is None:
            db.add(MunicipalityDB(municipality=municipality, province=province,
                                   latitude=latitude, longitude=longitude))
        else:
            row.province = province
            row.latitude = latitude
            row.longitude = longitude

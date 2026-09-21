"""System-administrator accounts, backed by the `superadmins` Postgres table
(app/db_models.py:SuperAdminDB). seed_if_empty() inserts the one dev account
on first startup, same as before this migration.

SuperAdmin sits above LGU_Tech: it can manage LGU accounts and view
cross-municipality data via app/routers/admin.py, instead of being scoped
to one assigned municipality.

Password is a bcrypt hash (see app/security.py). Plaintext dev credential,
for local testing only — rotate before any real deployment:
    sysadmin / PestWatch!FhkKbrMn6Y
"""

from app.db import session_scope
from app.db_models import SuperAdminDB
from app.schemas.auth import SuperAdminUser

_SEED_USERS = [
    SuperAdminUser(
        username="sysadmin",
        password_hash="$2b$12$B//.FDrrZpWaaWWR/V7LyuzLe4FwjpqychFbL0hYyugNMYl4hAncS",
        full_name="System Administrator",
    ),
]


def _to_schema(row: SuperAdminDB) -> SuperAdminUser:
    return SuperAdminUser(username=row.username, password_hash=row.password_hash, full_name=row.full_name)


def seed_if_empty() -> None:
    with session_scope() as db:
        if db.query(SuperAdminDB).first() is not None:
            return
        for user in _SEED_USERS:
            db.add(SuperAdminDB(**user.model_dump()))


def find_superadmin(username: str) -> SuperAdminUser | None:
    with session_scope() as db:
        row = db.get(SuperAdminDB, username)
        return _to_schema(row) if row else None

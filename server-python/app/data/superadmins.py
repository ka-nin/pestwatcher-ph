"""Hardcoded system-administrator accounts, held in-memory.

SuperAdmin sits above LGU_Tech: it can manage LGU accounts and view
cross-municipality data via app/routers/admin.py, instead of being scoped
to one assigned municipality. Replace with a real database table once
persistence is wired up (same caveat as app/data/lgu_users.py).

Password is a bcrypt hash (see app/security.py). Plaintext dev credential,
for local testing only — rotate before any real deployment:
    sysadmin / PestWatch!FhkKbrMn6Y
"""

from app.schemas.auth import SuperAdminUser

superadmins: list[SuperAdminUser] = [
    SuperAdminUser(
        username="sysadmin",
        password_hash="$2b$12$B//.FDrrZpWaaWWR/V7LyuzLe4FwjpqychFbL0hYyugNMYl4hAncS",
        full_name="System Administrator",
    ),
]


def find_superadmin(username: str) -> SuperAdminUser | None:
    return next((u for u in superadmins if u.username == username), None)

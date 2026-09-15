"""Hardcoded LGU municipal technician accounts, held in-memory.

Replace with a real database table once persistence is wired up — the
add/update/delete helpers below exist so app/routers/admin.py has a place
to make changes, but nothing here survives a server restart.

Passwords are bcrypt hashes (see app/security.py). Plaintext dev credentials,
for local testing only:
    munoz_tech_01    / PestWatch!Mu2026
    concepcion_tech  / PestWatch!Con2026
    sanmiguel_tech   / PestWatch!SM2026
    arayat_tech_01   / PestWatch!Ara2026
"""

from app.schemas.auth import LguUser

lgu_users: list[LguUser] = [
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


def municipality_coordinates(municipality: str) -> tuple[float, float] | None:
    """Looks up (latitude, longitude) for a municipality from the LGU
    accounts above, so live weather fetches don't need their own separate
    coordinate table. Replace with a real municipalities table once
    persistence is wired up (see module docstring)."""
    for user in lgu_users:
        if user.municipality == municipality:
            return user.latitude, user.longitude
    return None


def find_lgu_user(username: str) -> LguUser | None:
    return next((u for u in lgu_users if u.username == username), None)


def add_lgu_user(user: LguUser) -> None:
    if find_lgu_user(user.username) is not None:
        raise ValueError(f"LGU user '{user.username}' already exists")
    lgu_users.append(user)


def delete_lgu_user(username: str) -> bool:
    user = find_lgu_user(username)
    if user is None:
        return False
    lgu_users.remove(user)
    return True

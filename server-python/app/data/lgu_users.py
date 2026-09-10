"""Hardcoded LGU municipal technician accounts.

Mirrors server/src/data/lguUsers.ts from the legacy Node backend during migration.
Replace with a real database table once persistence is wired up.
"""

from app.schemas.auth import LguUser

lgu_users: list[LguUser] = [
    LguUser(
        username="munoz_tech_01",
        password="PestWatch!Mu2026",
        role_level="LGU_Tech",
        province="Nueva Ecija",
        municipality="Science City of Muñoz",
        latitude=15.7167,
        longitude=120.9167,
    ),
    LguUser(
        username="cabanatuan_tech",
        password="PestWatch!Cab2026",
        role_level="LGU_Tech",
        province="Nueva Ecija",
        municipality="Cabanatuan City",
        latitude=15.4864,
        longitude=120.9689,
    ),
    LguUser(
        username="concepcion_tech",
        password="PestWatch!Con2026",
        role_level="LGU_Tech",
        province="Tarlac",
        municipality="Concepcion",
        latitude=15.3167,
        longitude=120.6333,
    ),
    LguUser(
        username="sanmiguel_tech",
        password="PestWatch!SM2026",
        role_level="LGU_Tech",
        province="Bulacan",
        municipality="San Miguel",
        latitude=15.15,
        longitude=120.9667,
    ),
    LguUser(
        username="arayat_tech_01",
        password="PestWatch!Ara2026",
        role_level="LGU_Tech",
        province="Pampanga",
        municipality="Arayat",
        latitude=15.4167,
        longitude=120.7333,
    ),
]

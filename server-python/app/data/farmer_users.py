"""Placeholder B2C farmer accounts for the Expo mobile app.

Replace with a real database table (with hashed passwords) before launch.
These exist only so the unified /api/auth/login endpoint has something to
authenticate against while the mobile app is being built.
"""

from app.schemas.auth import FarmerUser

farmer_users: list[FarmerUser] = [
    FarmerUser(
        username="farmer_demo",
        password="RicePest!Demo2026",
        full_name="Demo Farmer",
        municipality="Science City of Muñoz",
        province="Nueva Ecija",
        latitude=15.7167,
        longitude=120.9167,
    ),
]

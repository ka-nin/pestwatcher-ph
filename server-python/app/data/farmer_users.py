"""Placeholder B2C farmer accounts for the Expo mobile app.

Replace with a real database table before launch. These exist only so the
unified /api/auth/login endpoint has something to authenticate against
while the mobile app is being built.

Passwords are bcrypt hashes (see app/security.py). Plaintext dev credential:
    farmer_demo / RicePest!Demo2026
"""

from app.schemas.auth import FarmerUser

farmer_users: list[FarmerUser] = [
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

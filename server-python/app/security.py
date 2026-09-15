"""Password hashing and JWT issuing/verification for the admin auth system.

Replaces the old plaintext-password comparison in app/routers/auth.py.
Tokens are stateless (no server-side session store) — a token is valid
until it expires, there is no revocation list. Fine for this thesis-scope
deployment; a real production system would want refresh tokens / a
revocation mechanism for logout-everywhere support.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt

from app.config import get_settings

Role = Literal["LGU_Tech", "SuperAdmin", "Farmer"]


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode(), password_hash.encode())
    except ValueError:
        return False


class TokenPayload:
    def __init__(self, username: str, role: Role):
        self.username = username
        self.role = role


def create_access_token(username: str, role: Role) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> TokenPayload | None:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None

    username = claims.get("sub")
    role = claims.get("role")
    if not username or role not in ("LGU_Tech", "SuperAdmin", "Farmer"):
        return None

    return TokenPayload(username=username, role=role)

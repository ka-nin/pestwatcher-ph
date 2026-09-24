from fastapi import Header, HTTPException

from app.security import TokenPayload, decode_access_token


def get_current_user(authorization: str | None = Header(default=None)) -> TokenPayload:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    claims = decode_access_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return claims


def require_superadmin(authorization: str | None = Header(default=None)) -> TokenPayload:
    user = get_current_user(authorization)
    if user.role != "SuperAdmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    return user


def require_lgu(authorization: str | None = Header(default=None)) -> TokenPayload:
    user = get_current_user(authorization)
    if user.role != "LGU_Tech":
        raise HTTPException(status_code=403, detail="LGU technician access required")
    return user

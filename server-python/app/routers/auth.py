from fastapi import APIRouter, HTTPException

from app.data.farmer_users import farmer_users
from app.data.lgu_users import lgu_users
from app.data.superadmins import superadmins
from app.schemas.auth import (
    FarmerAccountResponse,
    LguAccountResponse,
    LoginRequest,
    LoginResponse,
    SuperAdminAccountResponse,
)
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    superadmin_match = next(
        (u for u in superadmins if u.username == payload.username),
        None,
    )
    if superadmin_match and verify_password(payload.password, superadmin_match.password_hash):
        token = create_access_token(superadmin_match.username, "SuperAdmin")
        return LoginResponse(
            user=SuperAdminAccountResponse(username=superadmin_match.username, fullName=superadmin_match.full_name),
            accessToken=token,
        )

    lgu_match = next((u for u in lgu_users if u.username == payload.username), None)
    if lgu_match and verify_password(payload.password, lgu_match.password_hash):
        if not lgu_match.is_active:
            raise HTTPException(status_code=403, detail="This account has been deactivated")
        token = create_access_token(lgu_match.username, "LGU_Tech")
        return LoginResponse(
            user=LguAccountResponse(
                username=lgu_match.username,
                roleLevel=lgu_match.role_level,
                province=lgu_match.province,
                municipality=lgu_match.municipality,
                latitude=lgu_match.latitude,
                longitude=lgu_match.longitude,
            ),
            accessToken=token,
        )

    farmer_match = next((u for u in farmer_users if u.username == payload.username), None)
    if farmer_match and verify_password(payload.password, farmer_match.password_hash):
        token = create_access_token(farmer_match.username, "Farmer")
        return LoginResponse(
            user=FarmerAccountResponse(
                username=farmer_match.username,
                fullName=farmer_match.full_name,
                province=farmer_match.province,
                municipality=farmer_match.municipality,
                latitude=farmer_match.latitude,
                longitude=farmer_match.longitude,
            ),
            accessToken=token,
        )

    raise HTTPException(status_code=401, detail="Invalid username or password")

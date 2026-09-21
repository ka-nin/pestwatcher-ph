from fastapi import APIRouter, HTTPException

from app.data.farmer_users import find_farmer_user
from app.data.lgu_users import find_lgu_user
from app.data.superadmins import find_superadmin
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
    superadmin_match = find_superadmin(payload.username)
    if superadmin_match and verify_password(payload.password, superadmin_match.password_hash):
        token = create_access_token(superadmin_match.username, "SuperAdmin")
        return LoginResponse(
            user=SuperAdminAccountResponse(username=superadmin_match.username, fullName=superadmin_match.full_name),
            accessToken=token,
        )

    lgu_match = find_lgu_user(payload.username)
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

    farmer_match = find_farmer_user(payload.username)
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

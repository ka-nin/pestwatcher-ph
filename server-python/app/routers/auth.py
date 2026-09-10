from fastapi import APIRouter, HTTPException

from app.data.farmer_users import farmer_users
from app.data.lgu_users import lgu_users
from app.schemas.auth import (
    FarmerAccountResponse,
    LguAccountResponse,
    LoginRequest,
    LoginResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    lgu_match = next(
        (u for u in lgu_users if u.username == payload.username and u.password == payload.password),
        None,
    )
    if lgu_match:
        return LoginResponse(
            user=LguAccountResponse(
                username=lgu_match.username,
                role_level=lgu_match.role_level,
                province=lgu_match.province,
                municipality=lgu_match.municipality,
                latitude=lgu_match.latitude,
                longitude=lgu_match.longitude,
            )
        )

    farmer_match = next(
        (
            u
            for u in farmer_users
            if u.username == payload.username and u.password == payload.password
        ),
        None,
    )
    if farmer_match:
        return LoginResponse(
            user=FarmerAccountResponse(
                username=farmer_match.username,
                full_name=farmer_match.full_name,
                province=farmer_match.province,
                municipality=farmer_match.municipality,
                latitude=farmer_match.latitude,
                longitude=farmer_match.longitude,
            )
        )

    raise HTTPException(status_code=401, detail="Invalid username or password")

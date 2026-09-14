"""SuperAdmin-only endpoints: LGU account management, cross-municipality
overview, and a read-only view of the fixed ETL thresholds.

Every endpoint here requires a valid SuperAdmin JWT (see app/dependencies.py)
— this is the one part of the API that actually enforces authorization;
the rest of the API (inference/reports/weather) still trusts the caller,
same as before this router was added.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.data.lgu_users import add_lgu_user, delete_lgu_user, find_lgu_user, lgu_users
from app.decision.etl_thresholds import PEST_THRESHOLDS
from app.dependencies import require_superadmin
from app.routers.inference import _live_forecast
from app.schemas.admin import EtlThresholdsResponse, MunicipalityOverview, OverviewResponse
from app.schemas.auth import CreateLguUserRequest, LguAccountAdminResponse, LguUser, UpdateLguUserRequest
from app.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_superadmin)])

# Growth stage isn't tracked per-municipality anywhere yet (it's normally
# reported per-field by the LGU/farmer) — the overview uses a fixed stage
# so every municipality's forecast is at least comparable to each other.
OVERVIEW_GROWTH_STAGE = "Tillering"


def _to_admin_response(user: LguUser) -> LguAccountAdminResponse:
    return LguAccountAdminResponse(
        username=user.username,
        roleLevel=user.role_level,
        province=user.province,
        municipality=user.municipality,
        latitude=user.latitude,
        longitude=user.longitude,
        isActive=user.is_active,
    )


@router.get("/lgu-users", response_model=list[LguAccountAdminResponse])
def list_lgu_users() -> list[LguAccountAdminResponse]:
    return [_to_admin_response(u) for u in lgu_users]


@router.post("/lgu-users", response_model=LguAccountAdminResponse, status_code=201)
def create_lgu_user(payload: CreateLguUserRequest) -> LguAccountAdminResponse:
    if find_lgu_user(payload.username) is not None:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' is already taken")

    user = LguUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role_level=payload.role_level,
        province=payload.province,
        municipality=payload.municipality,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    add_lgu_user(user)
    return _to_admin_response(user)


@router.patch("/lgu-users/{username}", response_model=LguAccountAdminResponse)
def update_lgu_user(username: str, payload: UpdateLguUserRequest) -> LguAccountAdminResponse:
    user = find_lgu_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail=f"No LGU user '{username}'")

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role_level is not None:
        user.role_level = payload.role_level
    if payload.province is not None:
        user.province = payload.province
    if payload.municipality is not None:
        user.municipality = payload.municipality
    if payload.latitude is not None:
        user.latitude = payload.latitude
    if payload.longitude is not None:
        user.longitude = payload.longitude
    if payload.is_active is not None:
        user.is_active = payload.is_active

    return _to_admin_response(user)


@router.delete("/lgu-users/{username}", status_code=204)
def remove_lgu_user(username: str) -> None:
    if not delete_lgu_user(username):
        raise HTTPException(status_code=404, detail=f"No LGU user '{username}'")


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    """One BPH + RSB live forecast per municipality on file — the
    superadmin's cross-municipality view. Reuses the exact same pipeline
    /api/inference/forecast/live uses per municipality (see
    app/routers/inference.py's _live_forecast), so results always match
    what each LGU technician sees for their own municipality.
    """
    seen: set[str] = set()
    rows: list[MunicipalityOverview] = []

    for user in lgu_users:
        if user.municipality in seen:
            continue
        seen.add(user.municipality)

        rows.append(
            MunicipalityOverview(
                province=user.province,
                municipality=user.municipality,
                bph=_live_forecast(user.municipality, "BPH", OVERVIEW_GROWTH_STAGE),
                rsb=_live_forecast(user.municipality, "RSB", OVERVIEW_GROWTH_STAGE),
            )
        )

    return OverviewResponse(growthStageUsed=OVERVIEW_GROWTH_STAGE, municipalities=rows)


@router.get("/etl-thresholds", response_model=EtlThresholdsResponse)
def get_etl_thresholds() -> EtlThresholdsResponse:
    return EtlThresholdsResponse(
        thresholds={
            pest: {
                stage: {"lowMax": band.low_max, "highMin": band.high_min}
                for stage, band in stages.items()
            }
            for pest, stages in PEST_THRESHOLDS.items()
        }
    )

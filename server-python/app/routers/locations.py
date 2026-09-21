from app.data.lgu_users import list_lgu_users
from app.schemas.locations import MunicipalityOption
from fastapi import APIRouter

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("/municipalities", response_model=list[MunicipalityOption])
def list_municipalities() -> list[MunicipalityOption]:
    """Public list of municipalities the BiLSTM pest-forecast model covers.

    The mobile app has no farmer accounts — a farmer just picks their
    municipality on first launch instead of logging in — so this replaces
    the coordinates/municipality a login response used to carry. Sourced
    from the same LGU account records `municipality_coordinates()` uses,
    minus credentials, deduplicated by municipality.
    """
    seen: dict[str, MunicipalityOption] = {}
    for u in list_lgu_users():
        seen.setdefault(
            u.municipality,
            MunicipalityOption(
                municipality=u.municipality,
                province=u.province,
                latitude=u.latitude,
                longitude=u.longitude,
            ),
        )
    return list(seen.values())

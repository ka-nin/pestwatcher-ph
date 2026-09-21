from app.data.municipalities import list_municipalities
from app.schemas.locations import MunicipalityOption
from fastapi import APIRouter

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("/municipalities", response_model=list[MunicipalityOption])
def get_municipalities() -> list[MunicipalityOption]:
    """Public list of municipalities the BiLSTM pest-forecast model covers.

    The mobile app has no farmer accounts — a farmer just picks their
    municipality on first launch instead of logging in — so this replaces
    the coordinates/municipality a login response used to carry. Sourced
    from the `municipalities` table (app/data/municipalities.py), which is
    seeded independently of LGU accounts and grows as new LGU accounts are
    added, rather than being derived from whichever towns happen to have
    one right now.
    """
    return list_municipalities()

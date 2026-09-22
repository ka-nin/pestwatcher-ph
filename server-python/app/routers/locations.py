from app.data.municipalities import list_municipalities
from app.routers.inference import _live_forecast
from app.schemas.admin import MunicipalityOverview, OverviewResponse
from app.schemas.locations import MunicipalityOption
from fastapi import APIRouter

router = APIRouter(prefix="/api/locations", tags=["locations"])

# Growth stage isn't tracked per-farmer anywhere in the mobile app (there's
# no login, just a municipality picker) — mirrors OVERVIEW_GROWTH_STAGE in
# app/routers/admin.py so a municipality's risk reads the same whether a
# farmer or an LGU technician is looking at it.
RISK_OVERVIEW_GROWTH_STAGE = "Tillering"


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


@router.get("/municipalities/risk", response_model=OverviewResponse)
def get_municipalities_risk() -> OverviewResponse:
    """Public per-municipality BPH/RSB risk snapshot, for the mobile app's
    regional alerts list. Same fixed-growth-stage pipeline as the
    superadmin's /api/admin/overview (see app/routers/admin.py), just
    scoped to every municipality on file rather than only ones with an LGU
    account, and without the SuperAdmin auth requirement since the mobile
    app has no login at all.
    """
    rows = [
        MunicipalityOverview(
            province=m.province,
            municipality=m.municipality,
            bph=_live_forecast(m.municipality, "BPH", RISK_OVERVIEW_GROWTH_STAGE),
            rsb=_live_forecast(m.municipality, "RSB", RISK_OVERVIEW_GROWTH_STAGE),
        )
        for m in list_municipalities()
    ]
    return OverviewResponse(growthStageUsed=RISK_OVERVIEW_GROWTH_STAGE, municipalities=rows)

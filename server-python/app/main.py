from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.data.farmer_users import seed_if_empty as seed_farmer_users
from app.data.lgu_users import seed_if_empty as seed_lgu_users
from app.data.municipalities import seed_if_empty as seed_municipalities
from app.data.reports_store import backfill_pest_codes, migrate_from_json_if_empty
from app.data.superadmins import seed_if_empty as seed_superadmins
from app.db import init_db
from app.models.bilstm_model import bilstm_forecaster
from app.models.resnet_model import resnet_classifier
from app.routers import admin, auth, inference, locations, reports, weather
from ml.config import PEST_PARAMS

settings = get_settings()

app = FastAPI(title="Rice Pest Forecasting API", version="0.1.0")


@app.on_event("startup")
def init_database() -> None:
    """Creates tables if missing, then seeds them from what used to be
    hardcoded here (LGU/farmer/superadmin accounts) or in reports.json —
    a no-op once the database already has data. See app/db.py and
    app/data/*.py."""
    init_db()
    seed_lgu_users()
    seed_farmer_users()
    seed_superadmins()
    seed_municipalities()
    migrate_from_json_if_empty(Path(settings.upload_dir).parent / "reports.json")
    backfill_pest_codes()


@app.on_event("startup")
def load_ml_models() -> None:
    # Best-effort: a pest whose model hasn't been trained yet should leave
    # the API running (its forecast endpoint reports "model_not_loaded"),
    # not crash startup for every pest.
    # keras.models.load_model() raises ValueError (not FileNotFoundError/
    # OSError) for a missing .keras file — caught here too, or a single
    # untrained pest would take the whole app down at startup instead of
    # just leaving that pest reporting "model_not_loaded".
    for pest in PEST_PARAMS:
        try:
            bilstm_forecaster.load(pest)
        except (FileNotFoundError, OSError, ValueError):
            print(f"[startup] BiLSTM weights for {pest} not found — /api/inference/forecast will report model_not_loaded for {pest}")

        try:
            resnet_classifier.load(pest)
        except (FileNotFoundError, OSError, ValueError):
            print(f"[startup] ResNet-50 weights for {pest} not found — /api/inference/image will report model_not_loaded for {pest}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # admin-web's error handling expects {"message": ...} (legacy Node server shape)
    # rather than FastAPI's default {"detail": ...}.
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "Server is running smoothly"}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(weather.router)
app.include_router(inference.router)
app.include_router(reports.router)
app.include_router(locations.router)

# Serves farmer-uploaded report photos (app/routers/reports.py) so
# admin-web can render them directly as <img src>. Photos aren't behind
# auth — the mobile app's report submissions never carry a token (see
# app/data/farmer_users.py), so gating the photo itself wouldn't add
# real protection while admin-web's JWT layer (app/security.py) still
# needs to read them.
_uploads_dir = Path(settings.upload_dir)
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")

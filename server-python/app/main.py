from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import auth, inference, weather

settings = get_settings()

app = FastAPI(title="Rice Pest Forecasting API", version="0.1.0")

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
app.include_router(weather.router)
app.include_router(inference.router)

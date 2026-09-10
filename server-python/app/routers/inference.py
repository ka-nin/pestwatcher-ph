import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.models.resnet_model import resnet_classifier
from app.schemas.inference import (
    ForecastInferenceRequest,
    ForecastInferenceResponse,
    ImageInferenceResponse,
)
from app.models.bilstm_model import bilstm_forecaster

router = APIRouter(prefix="/api/inference", tags=["inference"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/image", response_model=ImageInferenceResponse)
async def infer_image(file: UploadFile = File(...)) -> ImageInferenceResponse:
    """Receives an optical field image from the mobile app for pest/disease detection.

    Wired up to `resnet_classifier`, which is currently a stub — see
    app/models/resnet_model.py for where to load the trained ResNet-50 weights.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}",
        )

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename or "").suffix or ".jpg"
    destination = upload_dir / f"{uuid.uuid4().hex}{extension}"

    contents = await file.read()
    destination.write_bytes(contents)

    result = resnet_classifier.predict(destination)

    return ImageInferenceResponse(
        status="ok" if result is not None else "model_not_loaded",
        pest_detected=result.label if result else None,
        confidence=result.confidence if result else None,
        risk_level=result.risk_level if result else None,
        message=(
            "Prediction successful"
            if result
            else "ResNet-50 model not loaded yet — image saved for later training/inference"
        ),
    )


@router.post("/forecast", response_model=ForecastInferenceResponse)
def infer_forecast(payload: ForecastInferenceRequest) -> ForecastInferenceResponse:
    """Takes engineered biological feature series (GDD/CRF/HP) and returns a
    projected outbreak peak. Wired up to `bilstm_forecaster`, currently a stub —
    see app/models/bilstm_model.py for where to load the trained BiLSTM weights.
    """
    result = bilstm_forecaster.predict(
        gdd_series=payload.gdd_series,
        crf_series=payload.crf_series,
        hp_series=payload.hp_series,
    )

    return ForecastInferenceResponse(
        status="ok" if result is not None else "model_not_loaded",
        peak_day_offset=result.peak_day_offset if result else None,
        projected_intensity=result.projected_intensity if result else None,
        message=(
            "Forecast successful"
            if result
            else "BiLSTM model not loaded yet — placeholder response"
        ),
    )

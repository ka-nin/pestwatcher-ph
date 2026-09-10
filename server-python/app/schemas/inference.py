from typing import Literal

from pydantic import BaseModel


class ImageInferenceResponse(BaseModel):
    """Response contract for the ResNet-50 optical field surveillance endpoint.

    Kept stable now so the mobile app can integrate against it before the
    real model is trained/loaded — `status` tells the caller whether the
    prediction is real or a placeholder.
    """

    status: Literal["ok", "model_not_loaded"]
    pest_detected: str | None = None
    confidence: float | None = None
    risk_level: Literal["Low", "Moderate", "High", "Critical"] | None = None
    message: str


class ForecastInferenceRequest(BaseModel):
    """Engineered feature sequence handed to the BiLSTM outbreak forecaster."""

    municipality: str
    gdd_series: list[float]
    crf_series: list[float]
    hp_series: list[float]


class ForecastInferenceResponse(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    peak_day_offset: int | None = None
    projected_intensity: float | None = None
    message: str

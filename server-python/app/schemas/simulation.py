"""SuperAdmin Simulation page: run a manually-entered 14-day weather window
(and optionally a pest photo) through BOTH the deployed engineered-feature
BiLSTM and the raw-feature baseline (the thesis's RQ2 control), side by
side, plus the real ResNet-50 classifier if a photo is supplied.

This is a live single-run demo, not a retest — `heldOutMetrics` carries the
already-computed historical performance (regression + ETL classification
agreement, both configurations) from ml/bilstm/compare_features.py's output,
shown as context next to the one-off prediction rather than recomputed.
"""

from typing import Literal

from pydantic import BaseModel

from app.schemas.inference import DailyWeatherObservation


class SimulationForecastRequest(BaseModel):
    pest: Literal["BPH", "RSB"]
    daily_observations: list[DailyWeatherObservation]


class SimulationModelResult(BaseModel):
    status: Literal["ok", "model_not_loaded"]
    predicted_value: float | None = None
    unit: Literal["hoppers_per_hill", "pct_damage"] | None = None
    risk_level: Literal["Low", "Medium", "High"] | None = None


class SimulationForecastResponse(BaseModel):
    pest: Literal["BPH", "RSB"]
    engineered: SimulationModelResult
    raw: SimulationModelResult
    # The already-computed CV comparison this pest's bilstm_{pest}_feature_comparison.json
    # holds (see ml/bilstm/compare_features.py) — null if that script hasn't been run.
    heldOutMetrics: dict | None = None


class SimulationImageResult(BaseModel):
    status: Literal["ok", "model_not_loaded", "no_pest_detected"]
    pest_detected: Literal["BPH", "RSB"] | None = None
    confidence: float | None = None
    pests_detected: list[Literal["BPH", "RSB"]] = []
    pest_scores: dict[str, float] = {}
    # The ResNet-50 held-out test metrics for whichever pest was detected
    # (or both pests, null if not detected) — same source as Model Insights.
    heldOutMetrics: dict[str, dict | None] | None = None

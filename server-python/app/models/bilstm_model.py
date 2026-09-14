"""BiLSTM outbreak-timing forecaster.

Loads the trained per-pest models produced by ml/bilstm/train.py
(ml/weights/{pest}/bilstm_{pest}.keras + matching *_scalers.joblib) and
turns a window of daily weather + growth-stage observations into the same
sequence/static feature vectors used at training time — see
ml/bilstm/build_sequences.py, which this mirrors. Both must stay in sync;
if the feature engineering there changes, update it here too.

predict() returns a continuous value only (hoppers/hill for BPH, % damage
for RSB). Bucketing that into Low/Medium/High happens in
app/decision/etl_thresholds.py, not here — see that module's docstring for
why the split matters (panel fix #1).
"""

from dataclasses import dataclass
from typing import Optional

import joblib
import numpy as np
from tensorflow import keras

from app.preprocessing.features import (
    calculate_crf,
    calculate_diurnal_range,
    calculate_gdd,
    calculate_hp,
    calculate_trend,
    calculate_vpd,
    calculate_wsi,
)
from ml.config import GROWTH_STAGE_BUCKETS, PEST_PARAMS

GROWTH_STAGES = ["Seedling", "Tillering", "Elongation", "Panicle", "Flowering", "Ripening"]


@dataclass
class DailyObservation:
    tmax: float
    tmin: float
    relative_humidity: float
    rainfall: float
    growth_stage: str


@dataclass
class BiLstmPrediction:
    predicted_value: float
    unit: str  # "hoppers_per_hill" (BPH) or "pct_damage" (RSB)


class BiLstmOutbreakForecaster:
    def __init__(self) -> None:
        self._models: dict[str, keras.Model] = {}
        self._scalers: dict[str, dict] = {}

    def load(self, pest: str) -> None:
        """Raises if the weights/scalers for `pest` haven't been trained yet
        (ml/bilstm/train.py --pest <pest>) — callers should catch this at
        startup rather than let it crash the whole app."""
        params = PEST_PARAMS[pest]
        self._models[pest] = keras.models.load_model(params.bilstm_weights_path)
        scalers_path = params.bilstm_weights_path.parent / f"bilstm_{pest.lower()}_scalers.joblib"
        self._scalers[pest] = joblib.load(scalers_path)

    def is_loaded(self, pest: str) -> bool:
        return pest in self._models

    def model_for(self, pest: str) -> keras.Model:
        """Exposes the raw Keras model — used by ml/explainability/shap_report.py,
        which needs direct model access to compute gradients rather than a
        single scalar prediction."""
        return self._models[pest]

    def scalers_for(self, pest: str) -> dict:
        return self._scalers[pest]

    def build_model_inputs(self, pest: str, window: list[DailyObservation]) -> tuple[np.ndarray, np.ndarray]:
        """The feature-engineering half of predict(): window -> scaled
        (X_sequence, X_static), without running the model. Split out so
        ml/explainability/shap_report.py can build the exact same inputs
        predict() would, without duplicating this logic."""
        params = PEST_PARAMS[pest]
        if len(window) != params.crf_window_days:
            raise ValueError(
                f"{pest} expects exactly {params.crf_window_days} consecutive daily "
                f"observations (most recent day last), got {len(window)}."
            )

        sequence_rows = []
        for day in window:
            vpd_daily = calculate_vpd([day.tmax], [day.tmin], [day.relative_humidity])
            diurnal_range_daily = calculate_diurnal_range([day.tmax], [day.tmin])
            stage_one_hot = [1.0 if day.growth_stage == stage else 0.0 for stage in GROWTH_STAGES]
            sequence_rows.append(
                [
                    day.tmax,
                    day.tmin,
                    day.relative_humidity,
                    day.rainfall,
                    vpd_daily,
                    diurnal_range_daily,
                    *stage_one_hot,
                ]
            )

        t_max = [d.tmax for d in window]
        t_min = [d.tmin for d in window]
        rh = [d.relative_humidity for d in window]
        rainfall = [d.rainfall for d in window]
        temp_mean_series = [(hi + lo) / 2 for hi, lo in zip(t_max, t_min)]

        gdd_accum = calculate_gdd(t_max, t_min, base_temp_c=params.gdd_base_temp_c)
        crf = calculate_crf(rainfall)
        hp = calculate_hp(rh, rh_threshold=params.hp_rh_threshold_pct)
        wsi = calculate_wsi(rainfall)
        rainfall_trend = calculate_trend(rainfall)
        temp_trend = calculate_trend(temp_mean_series)

        is_reproductive = 1.0 if GROWTH_STAGE_BUCKETS.get(window[-1].growth_stage) == "Reproductive" else 0.0
        reproductive_x_rainfall = is_reproductive * crf
        reproductive_x_temp = is_reproductive * (sum(temp_mean_series) / len(temp_mean_series))

        static_row = [
            gdd_accum,
            crf,
            hp,
            wsi,
            rainfall_trend,
            temp_trend,
            is_reproductive,
            reproductive_x_rainfall,
            reproductive_x_temp,
        ]

        scalers = self._scalers[pest]
        X_sequence = np.array([sequence_rows], dtype=np.float32)
        n, w, f = X_sequence.shape
        X_sequence_scaled = scalers["sequence_scaler"].transform(X_sequence.reshape(-1, f)).reshape(n, w, f)
        X_static_scaled = scalers["static_scaler"].transform(np.array([static_row], dtype=np.float32))
        return X_sequence_scaled, X_static_scaled

    def predict(self, pest: str, window: list[DailyObservation]) -> Optional[BiLstmPrediction]:
        if not self.is_loaded(pest):
            return None

        X_sequence_scaled, X_static_scaled = self.build_model_inputs(pest, window)

        prediction = self._models[pest].predict(
            {"sequence_input": X_sequence_scaled, "static_input": X_static_scaled},
            verbose=0,
        )
        predicted_value = float(prediction.flatten()[0])
        unit = "hoppers_per_hill" if pest == "BPH" else "pct_damage"
        return BiLstmPrediction(predicted_value=predicted_value, unit=unit)


bilstm_forecaster = BiLstmOutbreakForecaster()

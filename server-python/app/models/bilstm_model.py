"""BiLSTM outbreak-timing forecaster.

Takes engineered biological feature series (GDD, CRF, HP — see
app/preprocessing/features.py) and predicts when a pest outbreak will peak.

Drop your trained TensorFlow/Keras weights in and implement `load()` +
`predict()`. Until then, `predict()` returns None, which the
/api/inference/forecast route reports as `status: "model_not_loaded"`.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BiLstmPrediction:
    peak_day_offset: int
    projected_intensity: float


class BiLstmOutbreakForecaster:
    def __init__(self) -> None:
        self._model = None  # set by load() once trained weights exist

    def load(self) -> None:
        raise NotImplementedError("Load trained BiLSTM weights here before calling predict().")

    def predict(
        self,
        gdd_series: list[float],
        crf_series: list[float],
        hp_series: list[float],
    ) -> Optional[BiLstmPrediction]:
        if self._model is None:
            return None
        raise NotImplementedError


bilstm_forecaster = BiLstmOutbreakForecaster()

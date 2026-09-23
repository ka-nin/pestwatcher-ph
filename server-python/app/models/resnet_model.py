"""ResNet-50 optical field surveillance — pest presence classifiers.

Unlike app/models/bilstm_model.py (one continuous-value model per pest),
this is two independent BINARY classifiers, one per pest (BPH, RSB) — see
ml/resnet/train.py and ml/resnet/prepare_dataset.py for how each was
trained: positive = that pest's own annotated crops, negative = the other
tracked pest's crops plus four unrelated rice pests, so each model learns
to reject other insects rather than just distinguishing BPH vs RSB.

A photo is run through BOTH classifiers. If both report "not this pest",
nothing was detected. If one or both report "this pest present", whichever
has the higher positive-class confidence wins — there is no dedicated
"is it BPH or RSB" model, just two yes/no models compared against each
other.

This module only answers "which pest, if any, is in this photo" — it does
NOT produce a forecast. A 14-day outbreak trajectory requires 14 days of
weather (app/models/bilstm_model.py), which no single photo can supply;
see app/routers/inference.py's /image endpoint for how a detected pest here
triggers a separate BiLSTM forecast call for the farmer's municipality.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from PIL import Image
from tensorflow import keras

from ml.config import PEST_PARAMS

IMAGE_SIZE = (224, 224)
POSITIVE_THRESHOLD = 0.5  # matches the 0.5 cutoff used at training-time evaluation (ml/resnet/train.py)


@dataclass
class ResnetPrediction:
    # None means both loaded classifiers reported "not this pest" — a real,
    # expected outcome (e.g. a photo of a healthy plant), distinct from
    # predict() returning None outright when no model is loaded at all.
    label: Literal["BPH", "RSB"] | None
    confidence: float
    risk_level: Literal["Low", "Moderate", "High", "Critical"]


def _risk_level_for_confidence(confidence: float) -> Literal["Low", "Moderate", "High", "Critical"]:
    """Coarse, non-agronomic confidence banding for the raw image
    classification only — NOT the ETL-derived Low/Medium/High used
    elsewhere (app/decision/etl_thresholds.py), which is reserved for the
    BiLSTM's continuous forecast against PhilRice/DA-RCPC thresholds. This
    just tells the farmer how sure the photo-only detection is.
    """
    if confidence >= 0.9:
        return "Critical"
    if confidence >= 0.75:
        return "High"
    if confidence >= 0.6:
        return "Moderate"
    return "Low"


class ResNet50PestClassifier:
    def __init__(self) -> None:
        self._models: dict[str, keras.Model] = {}

    def load(self, pest: str) -> None:
        """Raises if resnet50_{pest}.keras hasn't been trained yet
        (ml/resnet/train.py --pest <pest>) — callers should catch this at
        startup rather than let it crash the whole app, same pattern as
        BiLstmOutbreakForecaster.load()."""
        weights_path = PEST_PARAMS[pest].resnet_weights_path
        self._models[pest] = keras.models.load_model(weights_path)

    def is_loaded(self, pest: str) -> bool:
        return pest in self._models

    def _positive_confidence(self, pest: str, image_array: np.ndarray) -> float:
        """Runs one pest's binary classifier; returns P(positive) — the
        model's raw sigmoid output, where class 1 is "positive" (see
        ml/resnet/train.py:load_datasets, class_names=["negative", "positive"])."""
        prediction = self._models[pest].predict(image_array, verbose=0)
        return float(prediction.flatten()[0])

    def predict(self, image_path: Path) -> Optional[ResnetPrediction]:
        """Returns None only if NEITHER model is loaded yet (mirrors the
        BiLSTM forecaster's "model_not_loaded" contract) — distinct from a
        real classification that found no pest, which returns a
        ResnetPrediction with label=None instead (see that field's
        docstring). If only one pest's model is loaded, prediction proceeds
        with just that one — a partially-trained deployment still returns
        useful results rather than an all-or-nothing failure.
        """
        loaded_pests = [pest for pest in PEST_PARAMS if self.is_loaded(pest)]
        if not loaded_pests:
            return None

        with Image.open(image_path) as img:
            img = img.convert("RGB").resize(IMAGE_SIZE)
            image_array = np.expand_dims(np.array(img, dtype=np.float32), axis=0)

        # Each pest's classifier was trained with resnet50.preprocess_input
        # (ml/resnet/train.py) — must match here or predictions are meaningless.
        from tensorflow.keras.applications import resnet50

        preprocessed = resnet50.preprocess_input(image_array.copy())

        confidences = {pest: self._positive_confidence(pest, preprocessed) for pest in loaded_pests}
        best_pest = max(confidences, key=confidences.get)
        best_confidence = confidences[best_pest]

        if best_confidence < POSITIVE_THRESHOLD:
            return ResnetPrediction(label=None, confidence=best_confidence, risk_level="Low")

        return ResnetPrediction(
            label=best_pest,
            confidence=best_confidence,
            risk_level=_risk_level_for_confidence(best_confidence),
        )


resnet_classifier = ResNet50PestClassifier()

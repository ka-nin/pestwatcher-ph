"""ResNet-50 optical field surveillance — per-pest binary classifiers.

Loads the trained crop-then-classify models produced by ml/resnet/train.py
(ml/weights/{pest}/resnet50_{pest}.keras) — one binary "is this pest in the
photo, yes or no" model per pest (BPH, RSB), not a single shared multi-class
model. See ml/resnet/prepare_dataset.py and train.py's docstrings for how
each one was built and why negatives include both the other target pest and
four unrelated rice pests.

predict() must preprocess exactly the way train.py did — resnet50's own
`preprocess_input` (ImageNet channel-mean subtraction), not a plain /255
scale — or a correctly-loaded model will silently produce garbage
predictions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from ml.config import PEST_PARAMS

IMAGE_SIZE = (224, 224)
POSITIVE_THRESHOLD = 0.5

RiskLevel = Literal["Low", "Moderate", "High", "Critical"]


@dataclass
class ResnetPrediction:
    label: str
    confidence: float
    risk_level: RiskLevel


class ResNet50PestClassifier:
    def __init__(self) -> None:
        self._models: dict[str, object] = {}  # pest -> loaded keras.Model

    def load(self, pest: str) -> None:
        """Raises if `pest`'s weights haven't been trained yet
        (ml/resnet/train.py --pest <pest>) — callers should catch this at
        startup rather than let it crash the whole app, same pattern as
        app/models/bilstm_model.py."""
        from tensorflow import keras

        params = PEST_PARAMS[pest]
        self._models[pest] = keras.models.load_model(params.resnet_weights_path)

    def is_loaded(self, pest: str) -> bool:
        return pest in self._models

    def predict(self, pest: str, image_path: Path) -> Optional[ResnetPrediction]:
        """Binary yes/no for one pest against one photo. Returns None if
        `pest`'s model isn't loaded (see is_loaded/load) rather than
        raising — "model_not_loaded" is a normal, expected state elsewhere
        in this API (e.g. /api/inference/forecast), and this mirrors it."""
        model = self._models.get(pest)
        if model is None:
            return None

        import numpy as np
        from PIL import Image
        from tensorflow.keras.applications import resnet50

        with Image.open(image_path) as img:
            img = img.convert("RGB").resize(IMAGE_SIZE)
            array = np.expand_dims(np.array(img), axis=0).astype("float32")

        array = resnet50.preprocess_input(array)
        positive_prob = float(model.predict(array, verbose=0)[0][0])

        is_positive = positive_prob >= POSITIVE_THRESHOLD
        confidence = positive_prob if is_positive else (1.0 - positive_prob)
        label = f"{pest} Detected" if is_positive else "Healthy"
        risk_level: RiskLevel = "High" if is_positive else "Low"

        return ResnetPrediction(label=label, confidence=confidence, risk_level=risk_level)

    def predict_best(self, image_path: Path) -> Optional[tuple[str, ResnetPrediction]]:
        """Runs every currently-loaded pest's classifier against one photo
        and returns the (pest, prediction) with the strongest positive
        detection — or the highest-confidence "Healthy" read if none of
        them fire positive. Used where the caller doesn't already know
        which pest to check for (the mobile Scan flow, and a report photo
        attached without — or regardless of — the farmer's own pest_type
        pick). Returns None only if no pest's model is loaded at all."""
        results = [(pest, self.predict(pest, image_path)) for pest in PEST_PARAMS if self.is_loaded(pest)]
        results = [(pest, pred) for pest, pred in results if pred is not None]
        if not results:
            return None

        positives = [(pest, pred) for pest, pred in results if pred.label != "Healthy"]
        candidates = positives or results
        return max(candidates, key=lambda item: item[1].confidence)


resnet_classifier = ResNet50PestClassifier()

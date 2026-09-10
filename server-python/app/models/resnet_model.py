"""ResNet-50 optical field surveillance model.

Drop your trained Keras/TensorFlow weights in and implement `load()` +
`predict()` below. Until then, `predict()` returns None, which the
/api/inference/image route reports as `status: "model_not_loaded"` so the
mobile app can already integrate against a stable contract.

Example of what `load()` will eventually look like:

    import tensorflow as tf

    def load(self) -> None:
        self._model = tf.keras.models.load_model("app/models/weights/resnet50_pest.h5")

And `predict()`:

    from PIL import Image
    import numpy as np

    def predict(self, image_path):
        if self._model is None:
            return None
        img = Image.open(image_path).convert("RGB").resize((224, 224))
        array = np.expand_dims(np.array(img) / 255.0, axis=0)
        probs = self._model.predict(array)[0]
        label_index = int(np.argmax(probs))
        return ResnetPrediction(
            label=self.labels[label_index],
            confidence=float(probs[label_index]),
            risk_level=self._risk_level_for(self.labels[label_index]),
        )
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


@dataclass
class ResnetPrediction:
    label: str
    confidence: float
    risk_level: Literal["Low", "Moderate", "High", "Critical"]


class ResNet50PestClassifier:
    labels = ["Healthy", "BPH Detected", "Dead Hearts", "Rice Blast"]

    def __init__(self) -> None:
        self._model = None  # set by load() once trained weights exist

    def load(self) -> None:
        raise NotImplementedError("Load trained ResNet-50 weights here before calling predict().")

    def predict(self, image_path: Path) -> Optional[ResnetPrediction]:
        if self._model is None:
            return None
        raise NotImplementedError


resnet_classifier = ResNet50PestClassifier()

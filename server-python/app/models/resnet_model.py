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

BPH photos bigger than one insect close-up are cut into a grid of tiles
first (app/preprocessing/tiling.py) and the BPH classifier scores each tile;
RSB always sees the whole photo, since its training photos are close-ups of
one large insect. Both pests are always scored, so a photo containing both
reports both (`pests_detected`), while `label` stays the single strongest one.

predict() must preprocess exactly the way train.py did — resnet50's own
`preprocess_input` (ImageNet channel-mean subtraction), not a plain /255
scale — or a correctly-loaded model will silently produce garbage
predictions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from PIL import Image
from tensorflow import keras

from app.preprocessing.tiling import (
    group_hits,
    make_tiles,
    needs_grid,
    prepare_for_grid,
)
from ml.config import PEST_PARAMS

IMAGE_SIZE = (224, 224)
POSITIVE_THRESHOLD = 0.5  # matches the 0.5 cutoff used at training-time evaluation (ml/resnet/train.py)

RiskLevel = Literal["Low", "Moderate", "High", "Critical"]


@dataclass
class ResnetPrediction:
    # None means both loaded classifiers reported "not this pest" — a real,
    # expected outcome (e.g. a photo of a healthy plant), distinct from
    # predict() returning None outright when no model is loaded at all.
    label: Literal["BPH", "RSB"] | None
    confidence: float
    risk_level: RiskLevel
    # Every loaded pest's own score, and every pest that cleared its own
    # cutoff (strongest first) — `label` is only the top one, so a photo
    # holding both BPH and RSB is visible here.
    pest_scores: dict[str, float] = field(default_factory=dict)
    pests_detected: list[str] = field(default_factory=list)
    # Set only when the BPH grid ran (photo bigger than one close-up): how
    # many tiles were scored and how many merged hit groups came out. An
    # approximate density hint, not an insect count — see tiling.py.
    grid_tiles: int | None = None
    grid_count: int | None = None


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

    def _positive_scores(self, pest: str, images: list[Image.Image]) -> list[float]:
        """Runs one pest's binary classifier on a batch of PIL images (each
        squeezed to 224x224); returns P(positive) per image — the model's raw
        sigmoid output, where class 1 is "positive" (see
        ml/resnet/train.py:load_datasets, class_names=["negative", "positive"]).
        Each classifier was trained with resnet50.preprocess_input, so that
        exact preprocessing is required here or predictions are meaningless."""
        from tensorflow.keras.applications import resnet50

        batch = np.stack([np.array(img.resize(IMAGE_SIZE), dtype=np.float32) for img in images])
        prediction = self._models[pest].predict(resnet50.preprocess_input(batch), batch_size=64, verbose=0)
        return [float(score) for score in prediction.flatten()]

    def _score_pest(self, pest: str, img: Image.Image) -> tuple[float, bool, int | None, int | None]:
        """(confidence, present, grid_tiles, grid_count) for one pest. Only
        BPH is ever gridded, and only when the photo is bigger than one
        insect close-up (app/preprocessing/tiling.py); everything else is a
        single whole-photo pass at the plain 0.5 cutoff."""
        if pest != "BPH" or not needs_grid(*img.size):
            confidence = self._positive_scores(pest, [img])[0]
            return confidence, confidence >= POSITIVE_THRESHOLD, None, None

        work = prepare_for_grid(img)
        tiles = make_tiles(*work.size)
        scores = self._positive_scores(
            pest, [work.crop((t.x, t.y, t.x + t.side, t.y + t.side)) for t in tiles]
        )
        groups = group_hits(tiles, scores)
        return max(scores), bool(groups), len(tiles), len(groups)

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

        with Image.open(image_path) as opened:
            img = opened.convert("RGB")

        confidences: dict[str, float] = {}
        present: dict[str, bool] = {}
        grid_tiles: int | None = None
        grid_count: int | None = None
        for pest in loaded_pests:
            confidences[pest], present[pest], tiles, groups = self._score_pest(pest, img)
            if tiles is not None:
                grid_tiles, grid_count = tiles, groups

        detected = sorted((pest for pest in loaded_pests if present[pest]), key=lambda pest: -confidences[pest])
        common = dict(pest_scores=confidences, pests_detected=detected, grid_tiles=grid_tiles, grid_count=grid_count)

        if not detected:
            return ResnetPrediction(
                label=None, confidence=max(confidences.values()), risk_level="Low", **common
            )

        best_pest = detected[0]
        return ResnetPrediction(
            label=best_pest,
            confidence=confidences[best_pest],
            risk_level=_risk_level_for_confidence(confidences[best_pest]),
            **common,
        )


resnet_classifier = ResNet50PestClassifier()

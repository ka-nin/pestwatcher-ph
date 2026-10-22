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
from ml.config import PEST_PARAMS, WEIGHTS_DIR

IMAGE_SIZE = (224, 224)
POSITIVE_THRESHOLD = 0.5  # matches the 0.5 cutoff used at training-time evaluation (ml/resnet/train.py)

# Separate bug-vs-no-bug detector consulted only when neither tracked pest
# fires (see ResnetPrediction.unidentified) — matches
# ml/resnet/train.py's UNKNOWN_WEIGHTS_PATH.
UNKNOWN_PEST_KEY = "UNKNOWN"
UNKNOWN_WEIGHTS_PATH = WEIGHTS_DIR / "unknown" / "resnet50_unknown.keras"

# Below POSITIVE_THRESHOLD but at or above this, "not BPH/RSB" is read as
# "something's there, just not a pest we're trained on" rather than "no
# insect at all" — e.g. one of the four unrelated rice pests, or a species
# the model has never seen. This is a confidence-based heuristic on top of
# an already-binary classifier, not a trained three-way distinction: the
# model was never fit on a "which pest, if any, excluding BPH/RSB" target,
# so it cannot name the organism, only flag that the photo didn't look like
# plain background either. The value itself is a starting point, not a
# validated boundary — ml/resnet/crops.py's background patches give a real
# no-insect population to check this threshold against before trusting it
# for anything beyond a softer UI message.
OTHER_PEST_THRESHOLD = 0.15

RiskLevel = Literal["Low", "Moderate", "High", "Critical"]


@dataclass
class ResnetPrediction:
    # None means every loaded tracked-pest classifier reported "not this
    # pest" AND the UNKNOWN bug-detector (if loaded) also found no insect —
    # a real, expected outcome (e.g. a photo of a healthy plant), distinct
    # from predict() returning None outright when no model is loaded at all.
    label: Literal["BPH", "RSB"] | None
    confidence: float
    risk_level: RiskLevel
    # True when no tracked pest (BPH/RSB) was detected, but the separate
    # UNKNOWN classifier found some insect in frame anyway (e.g. a
    # butterfly) — callers should report "unidentified pest detected"
    # rather than "no pest detected" in this case. Always False when
    # `label` is set.
    unidentified: bool = False
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
    # Only meaningful when label is None. True when the strongest score
    # still cleared OTHER_PEST_THRESHOLD — read as "an insect is probably
    # present, just not BPH or RSB" rather than "nothing here." See that
    # constant's docstring for exactly what this claim is and isn't.
    likely_other_pest: bool = False


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
        weights_path = UNKNOWN_WEIGHTS_PATH if pest == UNKNOWN_PEST_KEY else PEST_PARAMS[pest].resnet_weights_path
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
        """Returns None only if NEITHER tracked-pest model is loaded yet
        (mirrors the BiLSTM forecaster's "model_not_loaded" contract) —
        distinct from a real classification that found no pest, which
        returns a ResnetPrediction with label=None instead (see that
        field's docstring). If only one pest's model is loaded, prediction
        proceeds with just that one — a partially-trained deployment still
        returns useful results rather than an all-or-nothing failure.

        UNKNOWN (bug vs. no-bug) is consulted separately and only matters
        when neither tracked pest fires: it doesn't affect which tracked
        pest wins, just whether a non-detection is reported as "no pest"
        or "unidentified pest" (see ResnetPrediction.unidentified).
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
            unidentified = False
            if self.is_loaded(UNKNOWN_PEST_KEY):
                _, unidentified, _, _ = self._score_pest(UNKNOWN_PEST_KEY, img)
            top_score = max(confidences.values())
            return ResnetPrediction(
                label=None,
                confidence=top_score,
                risk_level="Low",
                unidentified=unidentified,
                likely_other_pest=top_score >= OTHER_PEST_THRESHOLD,
                **common,
            )

        best_pest = detected[0]
        return ResnetPrediction(
            label=best_pest,
            confidence=confidences[best_pest],
            risk_level=_risk_level_for_confidence(confidences[best_pest]),
            **common,
        )


resnet_classifier = ResNet50PestClassifier()


# (pest, target) -> trained file, from ml/resnet/train_regression.py. Separate
# from ResNet50PestClassifier because these are regressors (one continuous
# output) answering a different question — "how many / how much" — not the
# yes/no presence classifiers above; see that script's module docstring for
# why each needed its own training run (real counts for BPH, synthetic-only
# for coverage_pct/damage_pct).
REGRESSION_TARGETS: dict[tuple[str, str], Path] = {
    ("BPH", "count"): WEIGHTS_DIR / "bph" / "resnet50_bph_count.keras",
    ("BPH", "coverage_pct"): WEIGHTS_DIR / "bph" / "resnet50_bph_coverage_pct.keras",
    ("RSB", "damage_pct"): WEIGHTS_DIR / "rsb" / "resnet50_rsb_damage_pct.keras",
    # Field-level damage: trained on whole-field photos (ml/resnet/train_field_damage.py),
    # unlike the patch-level models above. Optional: absent until trained.
    ("BPH", "field_damage_pct"): WEIGHTS_DIR / "bph" / "resnet50_bph_field_damage_pct.keras",
    ("RSB", "field_damage_pct"): WEIGHTS_DIR / "rsb" / "resnet50_rsb_field_damage_pct.keras",
}


class ResNet50RegressorBank:
    """Loads and runs the photo-derived regressors the panel's redesign
    asked for: BPH hoppers-per-hill count + hectares-affected coverage %,
    RSB damage %. Each (pest, target) pair is an independent model, loaded
    only if its weights file exists — a deployment missing one of these
    still serves pest detection and the other regressors normally, same
    partial-availability principle as ResNet50PestClassifier.predict()."""

    def __init__(self) -> None:
        self._models: dict[tuple[str, str], keras.Model] = {}

    def load(self, pest: str, target: str) -> None:
        self._models[(pest, target)] = keras.models.load_model(REGRESSION_TARGETS[(pest, target)])

    def is_loaded(self, pest: str, target: str) -> bool:
        return (pest, target) in self._models

    def predict(self, pest: str, target: str, image_path: Path) -> float | None:
        if not self.is_loaded(pest, target):
            return None

        from tensorflow.keras.applications import resnet50

        with Image.open(image_path) as opened:
            img = opened.convert("RGB").resize(IMAGE_SIZE)
        batch = np.expand_dims(np.array(img, dtype=np.float32), axis=0)
        prediction = self._models[(pest, target)].predict(resnet50.preprocess_input(batch), verbose=0)
        return max(0.0, float(prediction.flatten()[0]))  # count/coverage/% can't be negative


    def predict_grid(self, pest: str, target: str, image_path: Path, rows: int, cols: int) -> list[list[float]] | None:
        """Runs the regressor on every cell of a rows x cols grid over one
        whole-field photo and returns the per-cell values (row-major).

        This is the panel's "sampling size" idea: the model was trained on
        photos framed like one patch of crop, so a field photo is cut into
        patch-sized cells, each cell is estimated on its own, and the mean
        over cells is the share of the whole photo affected. No pest
        classifier is involved; the caller says which pest to measure.
        """
        if not self.is_loaded(pest, target):
            return None

        from tensorflow.keras.applications import resnet50

        with Image.open(image_path) as opened:
            img = opened.convert("RGB")
        width, height = img.size
        cells = []
        for r in range(rows):
            for c in range(cols):
                box = (c * width // cols, r * height // rows, (c + 1) * width // cols, (r + 1) * height // rows)
                cells.append(np.array(img.crop(box).resize(IMAGE_SIZE), dtype=np.float32))
        predictions = self._models[(pest, target)].predict(resnet50.preprocess_input(np.stack(cells)), verbose=0)
        values = [max(0.0, float(v)) for v in predictions.flatten()]
        return [values[r * cols:(r + 1) * cols] for r in range(rows)]


resnet_regressors = ResNet50RegressorBank()

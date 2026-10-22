"""Finds each brown planthopper in a photo (RetinaNet, ResNet-50 backbone).

Trained by ml/detector/train_retinanet.py on the Roboflow brown planthopper set.
The scan uses it to draw a box on every insect and to report the count. The
weights are optional: until ml/weights/bph/retinanet_bph.pt exists (or if torch
is not installed) the detector is simply unavailable and the scan falls back
to the classifier and count regressor, exactly as before.
"""

from dataclasses import dataclass
from pathlib import Path

from ml.config import WEIGHTS_DIR

WEIGHTS_PATH = WEIGHTS_DIR / "bph" / "retinanet_bph_v2.pt"  # trained with background photos as negatives
# A box counts as an insect at or above this score. At 0.4 the detector counts closer to the
# truth than at 0.5 (it undercounts either way: about 55% of the insects are found) and still
# draws a box on only 10 of 62 photos that have no planthoppers.
SCORE_THRESHOLD = 0.4
# The detector alone may only turn a "no pest" photo into BPH when at least FLAG_MIN_BOXES
# boxes score at or above FLAG_SCORE. Measured on the same 62 non-BPH photos (healthy fields
# and stem borer damage) this gave 1 false flag, and it catches 3 of 20 true BPH test photos.
# Deliberately cautious.
FLAG_SCORE = 0.7
FLAG_MIN_BOXES = 3


@dataclass(frozen=True)
class Detection:
    x0: float
    y0: float
    x1: float
    y1: float
    score: float


class PlanthopperDetector:
    def __init__(self) -> None:
        self._model = None

    def load(self) -> None:
        """Raises if the weights or torch are missing; callers catch it at startup."""
        import torch

        from ml.detector.train_retinanet import build_model

        model = build_model(pretrained=False)
        model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu"))
        model.eval()
        self._model = model

    @staticmethod
    def confident(detections: list["Detection"] | None) -> bool:
        """Whether the boxes alone are enough to call the photo BPH."""
        return sum(d.score >= FLAG_SCORE for d in detections or []) >= FLAG_MIN_BOXES

    def is_loaded(self) -> bool:
        return self._model is not None

    def detect(self, image_path: Path, score_threshold: float = SCORE_THRESHOLD) -> list[Detection] | None:
        """Every planthopper box in the photo, or None when the detector is not loaded."""
        if self._model is None:
            return None
        import torch
        from PIL import Image
        from torchvision.transforms.functional import to_tensor

        with Image.open(image_path) as opened:
            tensor = to_tensor(opened.convert("RGB"))
        with torch.no_grad():
            out = self._model([tensor])[0]
        return [
            Detection(*(float(v) for v in box), float(score))
            for box, score in zip(out["boxes"], out["scores"])
            if float(score) >= score_threshold
        ]


planthopper_detector = PlanthopperDetector()

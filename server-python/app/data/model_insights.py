"""Assembles what admin-web's Model Insights page shows, from the artifacts the
training/evaluation scripts already write next to the model weights
(ml/weights/{bph,rsb}/): test metrics, per-sample BiLSTM predictions, SHAP
summaries, the BPH background-training comparison and the BPH grid test.
Any artifact that hasn't been generated yet comes back as null, and the page
shows a hint instead of failing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.bilstm_model import bilstm_forecaster
from app.models.resnet_model import resnet_classifier
from app.preprocessing.tiling import MIN_GROUP_TILES, TILE_HIT_THRESHOLD
from ml.config import PEST_PARAMS


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _modified_date(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except FileNotFoundError:
        return None


def build_model_insights() -> dict[str, Any]:
    models: list[dict[str, Any]] = []
    for pest, params in PEST_PARAMS.items():
        models.append(
            {
                "name": f"BiLSTM · {pest}",
                "detail": "hoppers/hill · 14-day window" if pest == "BPH" else "% damage · 14-day window",
                "loaded": bilstm_forecaster.is_loaded(pest),
                "updated": _modified_date(params.bilstm_weights_path),
            }
        )
    for pest, params in PEST_PARAMS.items():
        models.append(
            {
                "name": f"ResNet-50 · {pest}",
                "detail": "yes/no pest classifier",
                "loaded": resnet_classifier.is_loaded(pest),
                "updated": _modified_date(params.resnet_weights_path),
            }
        )

    resnet: dict[str, Any] = {}
    bilstm: dict[str, Any] = {}
    for pest, params in PEST_PARAMS.items():
        folder = params.bilstm_weights_path.parent
        key = pest.lower()
        resnet[pest] = _read_json(folder / f"resnet50_{key}_test_metrics.json")
        bilstm[pest] = {
            "metrics": _read_json(folder / f"bilstm_{key}_test_metrics.json"),
            "predictions": _read_json(folder / f"bilstm_{key}_test_predictions.json"),
            "shap": _read_json(folder / f"bilstm_{key}_shap_summary.json"),
            "featureComparison": _read_json(folder / f"bilstm_{key}_feature_comparison.json"),
        }

    bph_folder = PEST_PARAMS["BPH"].bilstm_weights_path.parent
    return {
        "models": models,
        "resnet": resnet,
        "bilstm": bilstm,
        "resnetBphComparison": _read_json(bph_folder / "resnet50_bph_background_comparison.json"),
        "grid": {
            "current": {"threshold": TILE_HIT_THRESHOLD, "minTiles": MIN_GROUP_TILES},
            "evaluation": _read_json(bph_folder / "resnet50_bph_grid_eval.json"),
        },
    }

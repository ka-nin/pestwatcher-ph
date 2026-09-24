"""Measures the BPH grid (app/preprocessing/tiling.py) on photos the BPH
classifier never saw, against the true annotated box counts.

Held-out = source images whose crops landed in the "test" split (same
filename hash as ml/resnet/prepare_dataset.py). Two kinds of input:
  * single photos (416px, as annotated) — BPH photos vs BPH-free photos
    (stem-borer and other-insect images), scored two ways: the whole photo
    squeezed to 224x224 ("whole") and cut into tiles ("grid");
  * 2x2 mosaics (832px) stitched from four held-out photos — a bigger scene
    with a known total: all-BPH, half-BPH, and BPH-free.

Tile scores are computed once per photo, so sweeping the tile-hit threshold
costs nothing. Reports, per threshold: presence recall, false-alarm rate on
BPH-free photos, and how the merged group count compares with the true box
count (MAE, correlation). The group count is a density hint, not an exact
insect count (two insects within a tile of each other merge into one group).

Run from server-python/ (about 20-30 min on CPU at the defaults):
    .venv/Scripts/python.exe -u -m ml.resnet.evaluate_grid
"""

import argparse
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image

from app.models.resnet_model import resnet_classifier
from app.preprocessing import tiling
from ml.config import PEST_PARAMS
from ml.resnet.crops import load_annotations
from ml.resnet.prepare_dataset import NEGATIVE_DIR, PEST_SOURCE_DIRS, split_bucket

THRESHOLDS = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]
MIN_TILES = [1, 2, 3, 4]
MOSAIC_SIDE = 416
SEED = 7


def held_out(folder: Path, prefix: str) -> list[Path]:
    return [
        p for p in sorted(folder.glob("*.jpg")) if split_bucket(f"{prefix}_{p.stem}_0.jpg") == "test"
    ]


def box_counts(folder: Path) -> dict[str, int]:
    return load_annotations(folder).groupby("filename").size().to_dict()


def score_photo(img: Image.Image) -> dict:
    work = tiling.prepare_for_grid(img)
    tiles = tiling.make_tiles(*work.size)
    scores = resnet_classifier._positive_scores(
        "BPH", [work.crop((t.x, t.y, t.x + t.side, t.y + t.side)) for t in tiles]
    )
    whole = resnet_classifier._positive_scores("BPH", [img])[0]
    return {"tiles": tiles, "scores": scores, "whole": whole}


def summarize(samples: list[dict]) -> dict:
    """samples: [{gt, tiles, scores, whole}]. gt == 0 means BPH-free."""
    pos = [s for s in samples if s["gt"] > 0]
    neg = [s for s in samples if s["gt"] == 0]
    out: dict = {"n_bph": len(pos), "n_bph_free": len(neg), "whole": {}, "grid": {}}

    if pos or neg:
        out["whole"] = {
            "recall_at_0.5": float(np.mean([s["whole"] >= 0.5 for s in pos])) if pos else None,
            "false_alarm_at_0.5": float(np.mean([s["whole"] >= 0.5 for s in neg])) if neg else None,
        }

    for thr, min_tiles in [(t, m) for t in THRESHOLDS for m in MIN_TILES]:
        counts = [len(tiling.group_hits(s["tiles"], s["scores"], thr, min_tiles)) for s in samples]
        gts = [s["gt"] for s in samples]
        pos_idx = [i for i, s in enumerate(samples) if s["gt"] > 0]
        neg_idx = [i for i, s in enumerate(samples) if s["gt"] == 0]
        row = {
            "recall": float(np.mean([counts[i] > 0 for i in pos_idx])) if pos_idx else None,
            "false_alarm": float(np.mean([counts[i] > 0 for i in neg_idx])) if neg_idx else None,
            "count_mae_on_bph": float(np.mean([abs(counts[i] - gts[i]) for i in pos_idx])) if pos_idx else None,
            "mean_groups_on_bph_free": float(np.mean([counts[i] for i in neg_idx])) if neg_idx else None,
            "correlation": float(np.corrcoef(counts, gts)[0, 1]) if len(set(counts)) > 1 and len(set(gts)) > 1 else None,
        }
        out["grid"][f"thr{thr}_min{min_tiles}"] = row
    return out


def fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "  n/a"
    return f"{v * 100:5.1f}%" if pct else f"{v:5.2f}"


def print_table(title: str, res: dict) -> None:
    print(f"\n=== {title}: {res['n_bph']} BPH photos, {res['n_bph_free']} BPH-free photos")
    w = res["whole"]
    print(f"  whole-photo @0.5  recall {fmt(w.get('recall_at_0.5'), True)}   false alarm {fmt(w.get('false_alarm_at_0.5'), True)}")
    print("  thr / min tiles | recall | false alarm | count MAE (BPH) | groups on BPH-free | corr(count, truth)")
    for name, r in res["grid"].items():
        label = name.replace("thr", "").replace("_min", " / ")
        print(
            f"  {label:>15} | {fmt(r['recall'], True)} | {fmt(r['false_alarm'], True):>11} | "
            f"{fmt(r['count_mae_on_bph']):>15} | {fmt(r['mean_groups_on_bph_free']):>18} | {fmt(r['correlation'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-single", type=int, default=60, help="held-out photos per group (BPH / BPH-free)")
    parser.add_argument("--n-mosaic", type=int, default=12, help="mosaics per kind (all-BPH / mixed / BPH-free)")
    args = parser.parse_args()

    resnet_classifier.load("BPH")
    rng = random.Random(SEED)

    bph_dir, sb_dir = PEST_SOURCE_DIRS["BPH"], PEST_SOURCE_DIRS["RSB"]
    bph_counts = box_counts(bph_dir)
    bph_pool = [p for p in held_out(bph_dir, "pos") if bph_counts.get(p.name, 0) > 0]
    free_pool = held_out(sb_dir, "otherpest") + held_out(NEGATIVE_DIR, "neg")
    print(f"held-out pools: {len(bph_pool)} BPH photos, {len(free_pool)} BPH-free photos")

    def load(p: Path) -> Image.Image:
        with Image.open(p) as im:
            return im.convert("RGB").resize((MOSAIC_SIDE, MOSAIC_SIDE))

    # ---- single photos
    singles: list[dict] = []
    for p in rng.sample(bph_pool, min(args.n_single, len(bph_pool))):
        singles.append({"gt": bph_counts[p.name], **score_photo(load(p))})
    for p in rng.sample(free_pool, min(args.n_single, len(free_pool))):
        singles.append({"gt": 0, **score_photo(load(p))})
    print(f"scored {len(singles)} single photos")
    single_res = summarize(singles)
    print_table("Single 416px photos", single_res)

    # ---- 2x2 mosaics
    def mosaic(paths: list[Path]) -> Image.Image:
        canvas = Image.new("RGB", (MOSAIC_SIDE * 2, MOSAIC_SIDE * 2))
        for i, p in enumerate(paths):
            canvas.paste(load(p), ((i % 2) * MOSAIC_SIDE, (i // 2) * MOSAIC_SIDE))
        return canvas

    mosaics: list[dict] = []
    for kind, n_bph in (("all-BPH", 4), ("mixed", 2), ("BPH-free", 0)):
        for _ in range(args.n_mosaic):
            picks = rng.sample(bph_pool, n_bph) + rng.sample(free_pool, 4 - n_bph)
            rng.shuffle(picks)
            gt = sum(bph_counts.get(p.name, 0) for p in picks)
            mosaics.append({"gt": gt, "kind": kind, **score_photo(mosaic(picks))})
    print(f"scored {len(mosaics)} mosaics")
    mosaic_res = summarize(mosaics)
    print_table("2x2 mosaics (832px)", mosaic_res)

    out_path = PEST_PARAMS["BPH"].resnet_weights_path.parent / "resnet50_bph_grid_eval.json"
    out_path.write_text(json.dumps({"single_416px": single_res, "mosaic_832px": mosaic_res}, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()

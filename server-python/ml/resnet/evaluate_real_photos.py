"""Scores the field-level damage model on REAL photos with a technologist's
measured damage %. This is the test the synthetic split cannot provide.

Input CSV columns: photo, pest, measured_pct   (path relative to the CSV, or absolute)
    photo,pest,measured_pct
    quadrat_001.jpg,RSB,35
    quadrat_002.jpg,RSB,6.5

Run from server-python/:
    .venv/bin/python -m ml.resnet.evaluate_real_photos path/to/measurements.csv

Reports RMSE, MAE, R², Pearson r and a per-photo table, per pest. It also
reports a "predict the mean" baseline: a model that does not beat it has not
learned to read damage. n below ~20 per pest is reported but flagged.
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

from app.models.resnet_model import resnet_regressors


def main(csv_path: Path) -> None:
    rows = list(csv.DictReader(csv_path.open()))
    by_pest: dict[str, list[tuple[str, float, float]]] = {}
    for pest in sorted({r["pest"] for r in rows}):
        try:
            resnet_regressors.load(pest, "field_damage_pct")
        except (OSError, ValueError):
            print(f"{pest}: no field damage model installed; train one first (ml/resnet/train_field_damage.py).")
            continue
        for r in rows:
            if r["pest"] != pest:
                continue
            path = Path(r["photo"]) if Path(r["photo"]).is_absolute() else csv_path.parent / r["photo"]
            cells = resnet_regressors.predict_grid(pest, "field_damage_pct", path)
            flat = [v for row in cells for v in row]
            by_pest.setdefault(pest, []).append((r["photo"], float(r["measured_pct"]), sum(flat) / len(flat)))

    report = {}
    for pest, items in by_pest.items():
        y = np.array([m for _, m, _ in items])
        p = np.array([q for _, _, q in items])
        err = p - y
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        report[pest] = {
            "n": len(items),
            "rmse": float(np.sqrt(np.mean(err**2))),
            "mae": float(np.mean(np.abs(err))),
            "r2": 1 - float(np.sum(err**2)) / ss_tot if ss_tot > 0 else None,
            "pearson_r": float(np.corrcoef(y, p)[0, 1]) if len(items) > 2 and p.std() > 0 and y.std() > 0 else None,
            "baseline_mae_predict_mean": float(np.mean(np.abs(y - y.mean()))),
            "small_sample": len(items) < 20,
        }
        print(f"\n{pest}: n={len(items)}" + ("  (small sample: under 20)" if len(items) < 20 else ""))
        for name, m, q in items:
            print(f"  {name:28s} measured {m:6.1f}   predicted {q:6.1f}")
        print("  " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in report[pest].items()}))
    (csv_path.parent / "real_photo_evaluation.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))

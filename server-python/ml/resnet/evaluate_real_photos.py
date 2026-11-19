"""Scores the photo scan on REAL field photos against an agricultural technologist's own reading.
This is the test the synthetic split cannot provide. Protocol: docs/real-photo-validation.md.

Each photo goes through the same POST /api/inference/image a farmer's scan uses, so what is
scored is what the app shows, not one model in isolation.

Input CSV (paths relative to the CSV, or absolute):
    photo,technologist_pest,measured_pct,measure
    field_001.jpg,BPH,,
    field_002.jpg,RSB,6.5,white_ears
    field_003.jpg,none,0,dead_hearts

  technologist_pest  what the technologist says the photo shows: BPH (insects or hopperburn),
                     RSB (dead hearts / white ears) or none (healthy)
  measured_pct       optional: the technologist's standard measurement for the hills in the frame
                     (RSB: dead hearts or white ears / total tillers x 100; BPH: hopperburned
                     hills / hills counted x 100)
  measure            optional: dead_hearts, white_ears or hopperburn_hills

Reports:
  1. The pest call: a confusion table of technologist vs app, the share called correctly, and
     each pest's recall (the hopperburn-called-RSB mistake shows up here).
  2. Damage agreement, per pest, on rows with a measurement: the app's severity is the share of the
     PHOTO covered by damage, the technologist's is a share of TILLERS or HILLS, so the two are not
     the same quantity. Rank agreement (Spearman) and Pearson r say whether the photo tracks the real
     damage; MAE is reported against a "predict the mean" baseline. Under 20 photos per pest is
     reported but flagged as too few.

Run from server-python/ (the database must be up, as for the app):
    PYTHONPATH=. .venv/bin/python -m ml.resnet.evaluate_real_photos path/to/measurements.csv
Output: real_photo_evaluation.json next to the CSV.
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from scipy import stats

from app.main import app

LABELS = ["BPH", "RSB", "none"]
MIN_PHOTOS = 20
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def app_call(body: dict) -> str:
    """The app's answer as one of LABELS: a pest, or none (healthy, unknown insect or no model)."""
    pest = body.get("pest_detected")
    return pest if pest in ("BPH", "RSB") else "none"


def scan(client: TestClient, path: Path) -> dict:
    with path.open("rb") as f:
        res = client.post(
            "/api/inference/image",
            files={"file": (path.name, f, CONTENT_TYPES.get(path.suffix.lower(), "image/jpeg"))},
        )
    res.raise_for_status()
    return res.json()


def pest_call_report(items: list[dict]) -> dict:
    matrix = {t: {p: 0 for p in LABELS} for t in LABELS}
    for item in items:
        matrix[item["technologist_pest"]][item["app_pest"]] += 1
    correct = sum(matrix[label][label] for label in LABELS)
    recall = {
        label: (matrix[label][label] / sum(matrix[label].values())) if sum(matrix[label].values()) else None
        for label in LABELS
    }
    return {"n": len(items), "accuracy": correct / len(items), "recall": recall, "confusion": matrix}


def damage_report(rows: list[tuple[str, float, float]]) -> dict:
    measured = np.array([m for _, m, _ in rows])
    app_value = np.array([a for _, _, a in rows])
    varied = len(rows) > 2 and measured.std() > 0 and app_value.std() > 0
    return {
        "n": len(rows),
        "too_few": len(rows) < MIN_PHOTOS,
        "spearman_rho": float(stats.spearmanr(measured, app_value).statistic) if varied else None,
        "pearson_r": float(np.corrcoef(measured, app_value)[0, 1]) if varied else None,
        "mae": float(np.mean(np.abs(app_value - measured))),
        "baseline_mae_predict_mean": float(np.mean(np.abs(measured - measured.mean()))),
        "note": "app severity is % of the photo; measured is % of tillers or hills: compare by agreement, not equality",
    }


def main(csv_path: Path) -> None:
    rows = list(csv.DictReader(csv_path.open()))
    items = []
    with TestClient(app) as client:
        for r in rows:
            truth = r["technologist_pest"].strip()
            if truth not in LABELS:
                raise SystemExit(f"{r['photo']}: technologist_pest must be one of {LABELS}, got {truth!r}")
            path = Path(r["photo"]) if Path(r["photo"]).is_absolute() else csv_path.parent / r["photo"]
            body = scan(client, path)
            fa = body.get("field_assessment") or {}
            items.append({
                "photo": r["photo"],
                "technologist_pest": truth,
                "app_pest": app_call(body),
                "app_status": body.get("status"),
                "app_severity_pct": fa.get("pct_affected"),
                "measured_pct": float(r["measured_pct"]) if r.get("measured_pct", "").strip() else None,
                "measure": r.get("measure", "").strip() or None,
            })

    report = {"pest_call": pest_call_report(items), "damage_agreement": {}, "photos": items}
    measures = {"RSB": {"dead_hearts", "white_ears"}, "BPH": {"hopperburn_hills"}}
    for pest in ("BPH", "RSB"):
        # This pest's photos, plus healthy photos measured the same way (their 0% anchors the scale).
        measured = [
            (i["photo"], i["measured_pct"], i["app_severity_pct"] or 0.0)
            for i in items
            if i["measured_pct"] is not None
            and (i["technologist_pest"] == pest or (i["technologist_pest"] == "none" and i["measure"] in measures[pest]))
        ]
        if measured:
            report["damage_agreement"][pest] = damage_report(measured)

    call = report["pest_call"]
    print(f"Pest call: {call['n']} photos, {100 * call['accuracy']:.0f}% correct" + ("  (too few photos)" if call["n"] < MIN_PHOTOS else ""))
    print("  technologist \\ app   " + "  ".join(f"{p:>5s}" for p in LABELS))
    for t in LABELS:
        print(f"  {t:20s} " + "  ".join(f"{call['confusion'][t][p]:5d}" for p in LABELS))
    for pest, d in report["damage_agreement"].items():
        print(f"{pest} damage: n={d['n']}{' (too few)' if d['too_few'] else ''}  spearman={d['spearman_rho']}  "
              f"pearson={d['pearson_r']}  mae={d['mae']:.2f} vs baseline {d['baseline_mae_predict_mean']:.2f}")
    out = csv_path.parent / "real_photo_evaluation.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"Saved to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))

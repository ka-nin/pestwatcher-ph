"""EXPERIMENT ONLY: did the learnable biological layer learn the biology?

Two checks on the trained models (ml/bilstm/bio_layer.py), run on windows the models never
saw (chronological test split), over several training runs with different random starts:

  1. THRESHOLDS: the humidity, rainfall and temperature levels each run settled on, in real
     units. If different random starts agree, the data pinned them down.
  2. GATE vs FORMULA: add up each learned gate over the 14 days and correlate it with the
     matching biological quantity (heat gate vs growing degree days, humid gate vs humidity
     persistence, dry gate vs water stress, wet gate vs cumulative rainfall). The formulas
     are calculated offline as an answer key only, never given to the model. The same
     check on the layer with RANDOM weights shows what training added.

Run from server-python/:
    PYTHONPATH=. .venv/bin/python -m ml.ablation.probe_bio_layer --pest BPH
Output: ml/weights/{pest}/bilstm_{pest}_bio_layer_probe.json
"""

import argparse
import json

import joblib
import numpy as np
from tensorflow import keras

from ml.ablation.probe_learned_features import answer_key
from ml.bilstm.bio_layer import LearnedBiologyGates
from ml.bilstm.train import build_model, chronological_split, load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

TAGS = ["bio", "bio2", "bio3", "bio4"]
PAIRS = {  # gate kind -> (answer key, how to add up the days)
    "heat": ("gdd", "sum"),
    "humid": ("hp", "mean"),
    "dry": ("wsi", "sum"),
    "wet": ("crf", "sum"),
}


def gate_outputs(model: keras.Model, X_scaled: np.ndarray, n_gates: int) -> dict[str, np.ndarray]:
    layer = model.get_layer("bio_gates")
    out = keras.Model(inputs=model.inputs[0], outputs=layer.output).predict(X_scaled, verbose=0, batch_size=512)
    gates = out[:, :, X_scaled.shape[2] :]  # drop the raw columns that were passed through
    names = ["heat", "humid", "dry", "wet"]
    return {k: gates[:, :, i * n_gates : (i + 1) * n_gates] for i, k in enumerate(names)}


def best_r2(window_value: np.ndarray, target: np.ndarray) -> float:
    """Highest squared correlation over the gate copies of one kind (a gate may be
    positively or negatively related; the sign does not matter for R-squared)."""
    best = 0.0
    for g in range(window_value.shape[1]):
        v = window_value[:, g]
        if np.std(v) < 1e-9:
            continue
        best = max(best, float(np.corrcoef(v, target)[0, 1] ** 2))
    return best


def score(model, X_scaled, key, test_idx, n_gates) -> dict:
    gates = gate_outputs(model, X_scaled[test_idx], n_gates)
    out = {}
    for kind, (target, how) in PAIRS.items():
        g = gates[kind]
        wv = g.sum(axis=1) if how == "sum" else g.mean(axis=1)
        out[f"{kind}_gate_vs_{target}"] = best_r2(wv, key[target][test_idx])
    return out


def run(pest: str) -> dict:
    params = PEST_PARAMS[pest]
    d = params.bilstm_weights_path.parent
    X_seq, _, _, meta, _, _ = load_dataset(pest, "plain_fresh")
    test_idx = chronological_split(meta, params.crf_window_days, FORECAST_HORIZON_DAYS)["test"]
    key = answer_key(X_seq[:, :, :4], pest)

    runs = []
    for tag in TAGS:
        sc = joblib.load(d / f"bilstm_{pest.lower()}_plain_fresh_{tag}_scalers.joblib")
        n, w, f = X_seq.shape
        X_scaled = sc["sequence_scaler"].transform(X_seq.reshape(-1, f)).reshape(n, w, f)
        model = keras.models.load_model(d / f"bilstm_{pest.lower()}_plain_fresh_{tag}.keras")
        layer = model.get_layer("bio_gates")
        runs.append(
            {
                "run": tag,
                "thresholds": layer.learned_thresholds(sc["sequence_scaler"].mean_[:4], sc["sequence_scaler"].scale_[:4]),
                "gate_vs_formula_r2_trained": score(model, X_scaled, key, test_idx, layer.n_gates),
            }
        )
        keras.utils.set_random_seed(abs(hash(tag)) % 1000)
        fresh = build_model(w, f, 3, bio_layer=True)
        runs[-1]["gate_vs_formula_r2_untrained"] = score(fresh, X_scaled, key, test_idx, layer.n_gates)
    return {"pest": pest, "windows_test": int(len(test_idx)), "runs": runs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    args = ap.parse_args()
    r = run(args.pest)
    out = PEST_PARAMS[args.pest].bilstm_weights_path.parent / f"bilstm_{args.pest.lower()}_bio_layer_probe.json"
    out.write_text(json.dumps(r, indent=2))
    print(f"{args.pest}: {r['windows_test']} test windows")
    for run_ in r["runs"]:
        t = run_["thresholds"]
        print(run_["run"], "humid level %", [round(x, 1) for x in t["humid_level_pct"]],
              "| dry level mm", [round(x, 1) for x in t["dry_rainfall_level_mm"]],
              "| wet level mm", [round(x, 1) for x in t["wet_rainfall_level_mm"]],
              "| heat base C", [round(x, 1) for x in t["heat_base_temperature_c"]])
    print(f"{'gate vs formula (R2)':28}{'trained (4 runs)':>34}{'untrained (4 runs)':>34}")
    for k in r["runs"][0]["gate_vs_formula_r2_trained"]:
        tr = [x["gate_vs_formula_r2_trained"][k] for x in r["runs"]]
        un = [x["gate_vs_formula_r2_untrained"][k] for x in r["runs"]]
        print(f"{k:28}{' '.join('%.2f' % v for v in tr):>34}{' '.join('%.2f' % v for v in un):>34}")

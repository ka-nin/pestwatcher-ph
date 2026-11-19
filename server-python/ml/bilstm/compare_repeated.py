"""The feature comparisons repeated over several random seeds, so a difference can be told apart
from training luck.

A single 5-fold run of one configuration moves by about as much as the differences being tested
(engineered BPH scored RMSE 7.78 in one run and 7.39 in another). This trains every configuration
on the same 5 expanding-window folds once per seed, then:

  per seed     the paired test on that seed's 5 folds, as compare_features.py reports it
  seed-averaged each fold's score averaged over the seeds, then the paired test on those 5 folds:
               the folds stay paired (same test block), and averaging removes most of the
               training noise, so this is the result to report

Configurations, all with the same targets and folds:
  raw          Tmax/Tmin/RH/rainfall only (the paper's baseline)
  seq_only     raw + growth stage
  engineered   seq_only + the hand-computed formulas (GDD, CRF, HP, WSI, trends, VPD, diurnal range)

Pairs:
  seq_only vs raw          what the growth stage adds
  engineered vs seq_only   what the formulas add, with the same information on both sides
  engineered vs raw        the paper's original RQ2 comparison

Run from server-python/ (about 30 minutes per pest with 3 seeds):
    PYTHONPATH=. .venv/bin/python -m ml.bilstm.compare_repeated --pest BPH
Output: ml/weights/{pest}/bilstm_{pest}_repeated_comparison.json
"""

import argparse
import json

import numpy as np
from tensorflow import keras

from ml.bilstm.compare_features import ALPHA, METRICS, N_FOLDS, expanding_window_folds, run_one, significance_test
from ml.bilstm.train import load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

CONFIGS = ["raw", "seq_only", "engineered"]
PAIRS = [("seq_only", "raw"), ("engineered", "seq_only"), ("engineered", "raw")]
REPORTED_METRICS = ["rmse", "mae", "r2", "f1_macro"]


def paired(a: list[float], b: list[float], metric: str, a_name: str, b_name: str) -> dict:
    """significance_test is written for "engineered" vs "raw"; relabel its output for any pair."""
    result = significance_test(a, b, metric)
    result[f"mean_{a_name}"] = result.pop("mean_engineered")
    result[f"mean_{b_name}"] = result.pop("mean_raw")
    result["better_configuration"] = {"engineered": a_name, "raw": b_name}[result["better_configuration"]]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    pest = args.pest

    data = {config: load_dataset(pest, config) for config in CONFIGS}
    y, meta = data["engineered"][2], data["engineered"][3]
    for config in CONFIGS:
        if not np.allclose(data[config][2], y):
            raise SystemExit(f"{config} and engineered sequences disagree on their targets: rebuild them.")
    is_reproductive = meta["is_reproductive"].to_numpy()
    order = meta["target_date"].sort_values().index.to_numpy()
    folds = expanding_window_folds(order, PEST_PARAMS[pest].crf_window_days + FORECAST_HORIZON_DAYS)

    # scores[seed][config] = one metrics dict per fold
    scores: dict[int, dict[str, list[dict[str, float]]]] = {}
    for seed in args.seeds:
        scores[seed] = {config: [] for config in CONFIGS}
        for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
            for config in CONFIGS:
                keras.utils.set_random_seed(seed * 100 + fold_number)  # same start for every configuration
                X_seq, X_static = data[config][0], data[config][1]
                result = run_one(pest, X_seq, X_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size)
                scores[seed][config].append(result)
                print(f"{pest} seed {seed} fold {fold_number} {config:10s} rmse={result['rmse']:.3f} mae={result['mae']:.3f}", flush=True)

    per_seed = {
        seed: {
            f"{a}_vs_{b}": {
                m: paired([f[m] for f in scores[seed][a]], [f[m] for f in scores[seed][b]], m, a, b)
                for m in REPORTED_METRICS
            }
            for a, b in PAIRS
        }
        for seed in args.seeds
    }

    # Each fold's score averaged over the seeds: still paired by fold, with the training noise averaged out.
    seed_avg = {
        config: [
            {m: float(np.mean([scores[seed][config][k][m] for seed in args.seeds])) for m in METRICS}
            for k in range(len(folds))
        ]
        for config in CONFIGS
    }
    seed_averaged_tests = {
        f"{a}_vs_{b}": {
            m: paired([f[m] for f in seed_avg[a]], [f[m] for f in seed_avg[b]], m, a, b) for m in REPORTED_METRICS
        }
        for a, b in PAIRS
    }

    run_to_run = {
        config: {
            m: {
                "mean_over_seeds": float(np.mean([np.mean([f[m] for f in scores[s][config]]) for s in args.seeds])),
                "sd_over_seeds": float(np.std([np.mean([f[m] for f in scores[s][config]]) for s in args.seeds], ddof=1)),
            }
            for m in REPORTED_METRICS
        }
        for config in CONFIGS
    }

    report = {
        "pest": pest,
        "seeds": args.seeds,
        "n_folds": N_FOLDS,
        "alpha": ALPHA,
        "epochs": args.epochs,
        "configs": {
            "raw": "Tmax/Tmin/RH/rainfall",
            "seq_only": "raw + growth stage",
            "engineered": "seq_only + hand-computed formulas",
        },
        "run_to_run": run_to_run,
        "seed_averaged_tests": seed_averaged_tests,
        "per_seed_tests": per_seed,
        "scores": {str(seed): s for seed, s in scores.items()},
    }
    out_path = PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_repeated_comparison.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== {pest}: seed-averaged paired tests over {N_FOLDS} folds x {len(args.seeds)} seeds ===")
    for pair, tests in seed_averaged_tests.items():
        a, b = pair.split("_vs_")
        for m in ("rmse", "mae"):
            t = tests[m]
            print(f"  {pair:24s} {m}: {t[f'mean_{a}']:.3f} vs {t[f'mean_{b}']:.3f}  p={t['p_value']:.4f}  significant={t['significant']}")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()

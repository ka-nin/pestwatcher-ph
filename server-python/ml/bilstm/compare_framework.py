"""Baseline BiLSTM vs. the proposed framework, as the panel framed it.

The 2026-10 consultation defined the comparison as: a baseline BiLSTM
WITHOUT the feature-engineering framework or image-derived inputs, against
the proposed framework WITH them. Neither existing comparison script is that:
compare_features.py is engineered vs raw (no image-derived input on either
side), and compare_seq_only.py is engineered vs seq_only (same). This one
trains all three configurations on the same folds:

  raw         baseline: Tmax/Tmin/RH/rainfall only, no static vector
  engineered  + biologically-informed features and growth stage
  lagged_fresh  + the latest technologist-verified observation and its age
                (the image-derived input; deployed since 2026-10-21). Half the
                windows have no report, the rest one aged 0-30 days, matching
                what the live system sees. The earlier `lagged` run (simulated
                ~14-day cadence) is kept in *_framework_comparison_lagged.json.

and tests two pairs:

  lagged vs raw         the full framework against the panel's baseline
  lagged vs engineered  what the verified observation adds on its own

Same method as compare_features.py: 5-fold expanding-window CV with a purge
gap, paired t-test or Wilcoxon per metric depending on Shapiro-Wilk, alpha
0.05. Every configuration sees the exact same test block in every fold.

Note on the observation input: in training it is drawn from the historical
CSV (see build_sequences.py's lagged_fresh), not from real farmer reports, of
which there are too few to train on. The result measures what the input is worth at that
simulated cadence, not what the live system currently achieves.

Prerequisites:
    .venv/bin/python -m ml.bilstm.build_sequences --features raw
    .venv/bin/python -m ml.bilstm.build_sequences
    .venv/bin/python -m ml.bilstm.build_sequences --features lagged

Run from server-python/:
    .venv/bin/python -m ml.bilstm.compare_framework --pest BPH
    .venv/bin/python -m ml.bilstm.compare_framework --pest RSB

Output: ml/weights/{pest}/bilstm_{pest}_framework_comparison.json
"""

import argparse
import json

import numpy as np
import pandas as pd

from ml.bilstm.compare_features import (
    ALPHA,
    METRICS,
    N_FOLDS,
    expanding_window_folds,
    run_one,
    significance_test,
)
from ml.bilstm.train import load_dataset
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

CONFIGS = ["raw", "engineered", "lagged_fresh"]
PAIRS = [("lagged_fresh", "raw"), ("lagged_fresh", "engineered")]


def relabel(test: dict, proposed: str, baseline: str) -> dict:
    """significance_test names its sides "engineered"/"raw"; rename them to
    the configurations actually being compared."""
    out = dict(test)
    if "mean_engineered" in out:
        out[f"mean_{proposed}"] = out.pop("mean_engineered")
        out[f"mean_{baseline}"] = out.pop("mean_raw")
    if "better_configuration" in out:
        out["better_configuration"] = proposed if out["better_configuration"] == "engineered" else baseline
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--folds",
        type=int,
        default=N_FOLDS,
        help="Number of expanding-window folds. With 5, the Wilcoxon fallback cannot reach p < 0.05 "
        "(its minimum two-sided p is 0.0625); 10 removes that floor.",
    )
    parser.add_argument(
        "--band-weight-power",
        type=float,
        default=None,
        help="Train every configuration with inverse-ETL-band sample weights at this power "
        "(same as train.py --balance-bands), so the comparison uses the deployed training recipe.",
    )
    parser.add_argument("--tag", default="", help="Suffix for the output file, e.g. 10fold_bw05.")
    parser.add_argument(
        "--proposed",
        choices=["lagged_fresh", "plain_fresh", "learned_fresh"],
        default="lagged_fresh",
        help="Which configuration is the proposed framework. plain_fresh = raw weather + growth stage "
        "+ the verified observation, no hand-computed formulas; it is compared with raw (the baseline) "
        "and with lagged_fresh (the same plus the formulas) to show what the formulas add.",
    )
    args = parser.parse_args()
    global CONFIGS, PAIRS
    if args.proposed == "plain_fresh":
        CONFIGS = ["raw", "lagged_fresh", "plain_fresh"]
        PAIRS = [("plain_fresh", "raw"), ("plain_fresh", "lagged_fresh")]
    if args.proposed == "learned_fresh":
        # The framework as built: raw inputs, with the biologically informed features learned by the
        # network (formulas only as training answers). Compared with raw and with the plain BiLSTM.
        CONFIGS = ["raw", "plain_fresh", "learned_fresh"]
        PAIRS = [("learned_fresh", "raw"), ("learned_fresh", "plain_fresh")]
    pest = args.pest

    data = {config: load_dataset(pest, "plain_fresh" if config == "learned_fresh" else config) for config in CONFIGS}
    _, _, y, meta, _, _ = data[CONFIGS[-1]]
    for config in CONFIGS:
        if len(data[config][2]) != len(y) or not np.allclose(data[config][2], y):
            raise SystemExit(f"{config} sequences disagree with engineered on targets; rebuild them.")

    is_reproductive = meta["is_reproductive"].to_numpy()
    order = meta["target_date"].sort_values().index.to_numpy()
    purge = PEST_PARAMS[pest].crf_window_days + FORECAST_HORIZON_DAYS
    folds = expanding_window_folds(order, purge, args.folds)

    per_fold: dict[str, list[dict[str, float]]] = {config: [] for config in CONFIGS}
    for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
        print(f"\n=== {pest} fold {fold_number}/{args.folds}: train={len(train_idx)} test={len(test_idx)}", flush=True)
        for config in CONFIGS:
            X_seq, X_static = data[config][0], data[config][1]
            scores = run_one(
                pest, X_seq, X_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size,
                args.band_weight_power,
                learned_features=0.6 if config == "learned_fresh" else None,
            )
            per_fold[config].append(scores)
            print(f"  {config:<11}" + "  ".join(f"{m}={scores[m]:.4f}" for m in METRICS), flush=True)

    significance = {}
    for proposed, baseline in PAIRS:
        significance[f"{proposed}_vs_{baseline}"] = {
            metric: relabel(
                significance_test(
                    [f[metric] for f in per_fold[proposed]], [f[metric] for f in per_fold[baseline]], metric
                ),
                proposed,
                baseline,
            )
            for metric in METRICS
        }

    mean_scores = {
        config: {metric: float(np.mean([f[metric] for f in folds_])) for metric in METRICS}
        for config, folds_ in per_fold.items()
    }
    report = {
        "pest": pest,
        "comparison": "raw (baseline) vs engineered vs lagged_fresh (proposed framework, deployed)",
        "n_folds": args.folds,
        "band_weight_power": args.band_weight_power,
        "alpha": ALPHA,
        "cross_validation": "expanding-window time-series, purge gap = window_days + horizon_days",
        "epochs": args.epochs,
        "lagged_observation_source": "historical CSV: 50% no report, else a report aged 0-30 days",
        "per_fold": per_fold,
        "mean_scores": mean_scores,
        "significance": significance,
    }
    suffix = f"_{args.tag}" if args.tag else ""
    out_path = PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_framework_comparison{suffix}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== {pest}: mean over {args.folds} folds ===")
    print(pd.DataFrame(mean_scores).to_string())
    for pair, tests in significance.items():
        print(f"\n--- {pair} ---")
        print(
            pd.DataFrame(
                {
                    "test": {m: tests[m]["test"] for m in METRICS},
                    "p_value": {m: round(tests[m]["p_value"], 4) for m in METRICS},
                    "significant": {m: tests[m]["significant"] for m in METRICS},
                    "better": {m: tests[m].get("better_configuration", "-") for m in METRICS},
                }
            ).to_string()
        )
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()

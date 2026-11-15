"""Can the BiLSTM learn the hand-computed biologically-informed features
itself, given only the raw daily climate series and growth stage, instead of
GDD/CRF/HP/WSI/trends handed to it pre-computed?

This is a second, narrower ablation alongside ml/bilstm/compare_features.py's
official `raw` control. That control strips growth stage too, which
confounds "can the LSTM learn the climate aggregation" with "does it also
lose phenology" — SHAP attributes ~45% of the engineered model's output to
growth stage alone (see bilstm_{pest}_shap_summary.json), so losing it would
swamp any effect from the climate features being tested. `seq_only` keeps
growth stage in the sequence and removes only what the panel's claim is
actually about: GDD, CRF, HP, WSI, the two trend features, and VPD/diurnal
range (both engineered quantities, not raw observations).

Same method as compare_features.py: 5-fold expanding-window time-series CV,
paired significance test per metric (paired t-test if Shapiro-Wilk says the
paired differences are normal, Wilcoxon signed-rank otherwise), alpha=0.05.

Prerequisites — build both feature sets first:
    .venv/bin/python -m ml.bilstm.build_sequences
    .venv/bin/python -m ml.bilstm.build_sequences --features seq_only

Run from server-python/:
    .venv/bin/python -m ml.bilstm.compare_seq_only --pest BPH
    .venv/bin/python -m ml.bilstm.compare_seq_only --pest RSB

Output: ml/weights/{pest}/bilstm_{pest}_seq_only_comparison.json. This is a
supplementary check, not a replacement for compare_features.py's official
Table 3 rows 2-3 — it answers a different, narrower question.
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    pest = args.pest

    eng_seq, eng_static, y, meta, _, _ = load_dataset(pest, "engineered")
    seqonly_seq, seqonly_static, y_so, meta_so, _, _ = load_dataset(pest, "seq_only")

    if len(y) != len(y_so) or not np.allclose(y, y_so):
        raise SystemExit(
            "Engineered and seq_only sequence sets disagree on their targets — rebuild both with "
            "ml.bilstm.build_sequences before comparing."
        )

    is_reproductive = meta["is_reproductive"].to_numpy()
    order = meta["target_date"].sort_values().index.to_numpy()
    purge = PEST_PARAMS[pest].crf_window_days + FORECAST_HORIZON_DAYS
    folds = expanding_window_folds(order, purge)

    per_fold: dict[str, list[dict[str, float]]] = {"engineered": [], "seq_only": []}

    for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
        print(f"\n=== {pest} fold {fold_number}/{N_FOLDS}: train={len(train_idx)} test={len(test_idx)}")

        engineered_scores = run_one(
            pest, eng_seq, eng_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size
        )
        seqonly_scores = run_one(
            pest, seqonly_seq, seqonly_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size
        )

        per_fold["engineered"].append(engineered_scores)
        per_fold["seq_only"].append(seqonly_scores)

        print(f"  engineered: " + "  ".join(f"{m}={engineered_scores[m]:.4f}" for m in METRICS))
        print(f"  seq_only:   " + "  ".join(f"{m}={seqonly_scores[m]:.4f}" for m in METRICS))

    # significance_test is written in terms of "engineered" vs "raw" labels;
    # reuse it as-is and just relabel the output, rather than forking it.
    tests = {
        metric: significance_test(
            [fold[metric] for fold in per_fold["engineered"]],
            [fold[metric] for fold in per_fold["seq_only"]],
            metric,
        )
        for metric in METRICS
    }
    for t in tests.values():
        t["mean_seq_only"] = t.pop("mean_raw")
        t["better_configuration"] = "seq_only" if t["better_configuration"] == "raw" else t["better_configuration"]

    report = {
        "pest": pest,
        "comparison": "engineered vs seq_only (raw climate + growth stage, no hand-computed aggregates)",
        "n_folds": N_FOLDS,
        "alpha": ALPHA,
        "cross_validation": "expanding-window time-series, purge gap = window_days + horizon_days",
        "epochs": args.epochs,
        "per_fold": per_fold,
        "mean_scores": {
            config: {metric: float(np.mean([f[metric] for f in folds_])) for metric in METRICS}
            for config, folds_ in per_fold.items()
        },
        "significance": tests,
    }

    out_path = PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_seq_only_comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== {pest}: engineered vs seq_only, {N_FOLDS}-fold expanding-window CV ===")
    summary = pd.DataFrame(
        {
            "engineered": report["mean_scores"]["engineered"],
            "seq_only": report["mean_scores"]["seq_only"],
            "test": {m: tests[m]["test"] for m in METRICS},
            "p_value": {m: round(tests[m]["p_value"], 4) for m in METRICS},
            "significant": {m: tests[m]["significant"] for m in METRICS},
        }
    )
    print(summary.to_string())
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()

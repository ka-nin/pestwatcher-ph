"""Engineered vs. raw climate features: the thesis's RQ2 and RQ3.

RQ2 asks how the BiLSTM trained on biologically-informed engineered features
compares against the SAME architecture trained on raw climate variables
(Tmax/Tmin/RH/rainfall only). RQ3 asks whether that difference is significant.
This script answers both, and writes the numbers that fill Table 3's rows 2
and 3.

Method, matching the paper's Statistical Treatment section:

  1. Time-Series Cross-Validation, expanding window, 5 sequential folds.
     Samples are ordered by target date and cut into 6 contiguous blocks.
     Fold k trains on blocks 0..k and tests on block k+1, so the training
     window grows chronologically and every test block is strictly in the
     future of its training data. A purge gap of (window_days + horizon_days)
     samples is dropped at each boundary, because sliding windows overlap and
     a train sample's target date could otherwise sit inside a test sample's
     input window.

  2. Both configurations are evaluated on the EXACT SAME test block in every
     fold, which is what makes the two score vectors paired data and licenses
     the paired test in step 4.

  3. Seven metrics per fold per configuration: RMSE, MAE and R2 for the
     continuous forecast, then Accuracy, Precision, Recall and F1 for the
     Low/Medium/High bands the ETL table derives from it
     (ml/bilstm/etl_metrics.py). Precision/recall/F1 are macro-averaged.

  4. For each metric, the 5 paired differences are checked for normality with
     Shapiro-Wilk. If normal (p >= 0.05) a paired-samples t-test is reported;
     otherwise the non-parametric Wilcoxon signed-rank test is, exactly as the
     paper's fallback rule specifies. Significance is judged at alpha = 0.05.

Prerequisites — build BOTH feature sets first:
    .venv/Scripts/python.exe -m ml.bilstm.build_sequences
    .venv/Scripts/python.exe -m ml.bilstm.build_sequences --features raw

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.compare_features --pest BPH
    .venv/Scripts/python.exe -m ml.bilstm.compare_features --pest RSB

This trains 2 models per fold (10 per pest), so expect it to take a while;
--epochs is lowered from train.py's default for that reason. Output goes to
ml/weights/{pest}/bilstm_{pest}_feature_comparison.json and is read by nothing
else — it is evidence for the paper, not a runtime artifact.
"""

import argparse
import json

import numpy as np
import pandas as pd
from scipy import stats
from tensorflow import keras

from ml.bilstm.etl_metrics import classification_agreement
from ml.bilstm.train import (
    build_model,
    load_dataset,
    model_inputs,
    predict,
    regression_metrics,
    scale_sequence,
    scale_static,
)
from ml.config import FORECAST_HORIZON_DAYS, PEST_PARAMS

N_FOLDS = 5
ALPHA = 0.05
VAL_FRACTION_OF_TRAIN = 0.15

# Lower is better for these; higher is better for the rest. Only affects how
# the "which configuration won" line is phrased, never the test itself.
LOWER_IS_BETTER = {"rmse", "mae"}

METRICS = ["rmse", "mae", "r2", "accuracy", "precision_macro", "recall_macro", "f1_macro"]


def expanding_window_folds(order: np.ndarray, purge: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """(train_idx, test_idx) per fold, over an array of row indices already
    sorted by target date. Block k+1 is the test set; blocks 0..k are training,
    minus a purge gap at the join."""
    n = len(order)
    block_size = n // (N_FOLDS + 1)

    folds = []
    for k in range(N_FOLDS):
        train_end = block_size * (k + 1)
        test_start = train_end
        test_end = test_start + block_size if k < N_FOLDS - 1 else n

        train_idx = order[: max(train_end - purge, 0)]
        test_idx = order[test_start:test_end]
        folds.append((train_idx, test_idx))
    return folds


def run_one(
    pest: str,
    X_sequence: np.ndarray,
    X_static: np.ndarray,
    y: np.ndarray,
    is_reproductive: np.ndarray,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    epochs: int,
    batch_size: int,
) -> dict[str, float]:
    """Trains one configuration on one fold and returns its seven metrics.

    The tail of the training block becomes the validation set for early
    stopping. It is carved off chronologically (not sampled) so validation
    stays in the future of training, same as the test block is.
    """
    val_size = int(len(train_idx) * VAL_FRACTION_OF_TRAIN)
    fit_idx, val_idx = train_idx[:-val_size], train_idx[-val_size:]

    X_seq_fit, X_seq_val, X_seq_test, _ = scale_sequence(
        X_sequence[fit_idx], X_sequence[val_idx], X_sequence[test_idx]
    )
    X_static_fit, X_static_val, X_static_test, _ = scale_static(
        X_static[fit_idx], X_static[val_idx], X_static[test_idx]
    )

    keras.backend.clear_session()
    model = build_model(
        window_days=X_sequence.shape[1],
        n_seq_features=X_sequence.shape[2],
        n_static_features=X_static.shape[1],
    )
    model.fit(
        model_inputs(X_seq_fit, X_static_fit),
        y[fit_idx],
        validation_data=(model_inputs(X_seq_val, X_static_val), y[val_idx]),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)],
        verbose=0,
    )

    y_true = y[test_idx]
    y_pred = predict(model, X_seq_test, X_static_test)
    etl = classification_agreement(pest, y_true, y_pred, is_reproductive[test_idx])

    return {
        **regression_metrics(y_true, y_pred),
        "accuracy": etl["accuracy"],
        "precision_macro": etl["precision_macro"],
        "recall_macro": etl["recall_macro"],
        "f1_macro": etl["f1_macro"],
    }


def significance_test(engineered: list[float], raw: list[float], metric: str) -> dict:
    """Paired t-test, or Wilcoxon signed-rank when the paired differences fail
    Shapiro-Wilk — the paper's stated fallback."""
    differences = np.array(engineered) - np.array(raw)

    if np.allclose(differences, 0):
        return {
            "test": "none",
            "reason": "All paired differences are zero — the two configurations scored identically.",
            "p_value": 1.0,
            "significant": False,
        }

    shapiro_stat, shapiro_p = stats.shapiro(differences)
    normal = bool(shapiro_p >= ALPHA)

    if normal:
        statistic, p_value = stats.ttest_rel(engineered, raw)
        test_name = "paired t-test"
    else:
        statistic, p_value = stats.wilcoxon(engineered, raw)
        test_name = "Wilcoxon signed-rank"

    mean_engineered, mean_raw = float(np.mean(engineered)), float(np.mean(raw))
    if metric in LOWER_IS_BETTER:
        better = "engineered" if mean_engineered < mean_raw else "raw"
    else:
        better = "engineered" if mean_engineered > mean_raw else "raw"

    return {
        "test": test_name,
        "shapiro_p": float(shapiro_p),
        "paired_differences_normal": normal,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "significant": bool(p_value < ALPHA),
        "mean_engineered": mean_engineered,
        "mean_raw": mean_raw,
        "mean_difference": float(np.mean(differences)),
        "better_configuration": better,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pest", choices=["BPH", "RSB"], required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    pest = args.pest

    eng_seq, eng_static, y, meta, _, _ = load_dataset(pest, "engineered")
    raw_seq, raw_static, y_raw, meta_raw, _, _ = load_dataset(pest, "raw")

    # Both configurations are built from the same rows in the same order by
    # build_sequences.py; if that ever stops being true the pairing is invalid
    # and so is the whole test, so fail loudly rather than silently compare
    # misaligned folds.
    if len(y) != len(y_raw) or not np.allclose(y, y_raw):
        raise SystemExit(
            "Engineered and raw sequence sets disagree on their targets — rebuild both with "
            "ml.bilstm.build_sequences before comparing."
        )

    is_reproductive = meta["is_reproductive"].to_numpy()
    order = meta["target_date"].sort_values().index.to_numpy()
    purge = PEST_PARAMS[pest].crf_window_days + FORECAST_HORIZON_DAYS
    folds = expanding_window_folds(order, purge)

    per_fold: dict[str, list[dict[str, float]]] = {"engineered": [], "raw": []}

    for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
        print(f"\n=== {pest} fold {fold_number}/{N_FOLDS}: train={len(train_idx)} test={len(test_idx)}")

        engineered_scores = run_one(
            pest, eng_seq, eng_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size
        )
        raw_scores = run_one(
            pest, raw_seq, raw_static, y, is_reproductive, train_idx, test_idx, args.epochs, args.batch_size
        )

        per_fold["engineered"].append(engineered_scores)
        per_fold["raw"].append(raw_scores)

        print(f"  engineered: " + "  ".join(f"{m}={engineered_scores[m]:.4f}" for m in METRICS))
        print(f"  raw:        " + "  ".join(f"{m}={raw_scores[m]:.4f}" for m in METRICS))

    tests = {
        metric: significance_test(
            [fold[metric] for fold in per_fold["engineered"]],
            [fold[metric] for fold in per_fold["raw"]],
            metric,
        )
        for metric in METRICS
    }

    report = {
        "pest": pest,
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

    out_path = PEST_PARAMS[pest].bilstm_weights_path.parent / f"bilstm_{pest.lower()}_feature_comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n=== {pest}: engineered vs raw, {N_FOLDS}-fold expanding-window CV ===")
    summary = pd.DataFrame(
        {
            "engineered": report["mean_scores"]["engineered"],
            "raw": report["mean_scores"]["raw"],
            "test": {m: tests[m]["test"] for m in METRICS},
            "p_value": {m: round(tests[m]["p_value"], 4) for m in METRICS},
            "significant": {m: tests[m]["significant"] for m in METRICS},
        }
    )
    print(summary.to_string())
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()

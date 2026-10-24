"""Computational-efficiency comparison: baseline BiLSTM vs. the deployed
engineered-feature framework, and the seq_only ablation alongside them —
training time, inference latency, and peak memory, not just accuracy.

Directly answers the panel's point that forecasting-performance comparisons
alone don't establish whether the proposed framework's extra preprocessing
is computationally justified. Each (pest, feature_set) runs training ONCE
(chronological split, same as the deployed model's own training — not the
5-fold CV ml/bilstm/compare_features.py uses for the significance tests,
since repeating training 5x per config here would multiply wall-clock cost
for a question that doesn't need paired folds to answer) in its OWN process,
wrapped with `/usr/bin/time -l` (macOS) so peak memory is measured cleanly
per run rather than carried over from whichever config happened to run
first in a shared session.

Prerequisites — same sequence files compare_features.py and
compare_seq_only.py already need:
    .venv/bin/python -m ml.bilstm.build_sequences
    .venv/bin/python -m ml.bilstm.build_sequences --features raw
    .venv/bin/python -m ml.bilstm.build_sequences --features seq_only

Run from server-python/:
    .venv/bin/python -m ml.bilstm.benchmark_efficiency

Output: ml/weights/bilstm_efficiency_benchmark.json (pooled across both
pests — this one isn't per-pest like the others, since the point is a
system-wide time/memory comparison, not a forecasting-accuracy one).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PESTS = ["BPH", "RSB"]
FEATURE_SETS = ["raw", "plain_fresh", "lagged_fresh"]

OUT_PATH = Path(__file__).resolve().parents[1] / "weights" / "bilstm_efficiency_benchmark.json"

MEMORY_LINE = re.compile(r"(\d+)\s+peak memory footprint")


def run_one(pest: str, features: str) -> dict:
    print(f"=== {pest} / {features} ===", file=sys.stderr)
    proc = subprocess.run(
        ["/usr/bin/time", "-l", sys.executable, "-m", "ml.bilstm.benchmark_one_config", "--pest", pest, "--features", features],
        capture_output=True,
        text=True,
        check=True,
    )
    # stdout: the one JSON line from benchmark_one_config.py (TF's own
    # startup noise, if any, goes to stderr, not stdout, so this is safe to
    # parse directly rather than hunting for a line that starts with "{").
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    match = MEMORY_LINE.search(proc.stderr)
    result["peak_memory_bytes"] = int(match.group(1)) if match else None
    result["peak_memory_mb"] = round(int(match.group(1)) / (1024 * 1024), 1) if match else None

    print(
        f"  train={result['train_seconds']:.1f}s ({result['epochs_run']} epochs)  "
        f"inference={result['inference_latency_ms_mean']:.1f}ms  "
        f"mem={result['peak_memory_mb']}MB  "
        f"rmse={result['rmse']:.3f} r2={result['r2']:.3f}",
        file=sys.stderr,
    )
    return result


def main() -> None:
    rows = [run_one(pest, features) for pest in PESTS for features in FEATURE_SETS]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2))
    print(f"\nSaved to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()

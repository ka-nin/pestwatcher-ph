"""Formal validity test for the BiLSTM outbreak forecaster — run after every
training run (ml/bilstm/train.py) to produce a pass/fail verdict with the
evidence behind it, for the thesis's validity-testing requirement.

Two independent checks, because a model can pass one and still fail the
other:

  1. STATISTICAL VALIDITY — the already-saved held-out test-set regression
     metrics (RMSE/MAE/R2, from ml/bilstm/train.py's evaluate()) against a
     stated acceptance threshold. This answers "is the model's fit to its
     own held-out data good enough to trust," using data the model never
     trained on but that still comes from the same historical dataset.

  2. FIELD VALIDITY — live predictions compared against LGU-verified farmer
     reports (the same comparison GET /api/inference/gap-analysis exposes
     per-municipality, aggregated here across every municipality on file).
     This answers "does the model's Low/Medium/High call agree with what
     actually happened in the field," which the statistical check alone
     cannot show — the test split is historical weather-derived ground
     truth, not independent real-world confirmation.

Neither check changes anything: this is read-only, the same as
GET /api/inference/gap-analysis (see app/routers/inference.py's
_run_forecast docstring for why verified reports never feed back into a
live prediction). A failing verdict here is a signal to retrain or revisit
the architecture, not something this script acts on itself.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.validity_test
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import date

from app.data.lgu_users import list_lgu_users
from app.routers.inference import infer_gap_analysis
from ml.config import PEST_PARAMS

# Acceptance thresholds — deliberately conservative placeholders; tighten
# once the thesis's own target accuracy figures are finalized. R2 close to
# 0 means "no better than predicting the mean," which is the real floor for
# a regression model to be worth deploying at all.
MIN_R2 = 0.3
MAX_MAE_FRACTION_OF_HIGH_MIN = 0.5  # MAE must be well under the High-risk cutoff to be useful for ETL bucketing

# Field validity: the gap-analysis agreement rate across every municipality,
# over the trailing 14 days, must clear this fraction of comparable days.
MIN_FIELD_AGREEMENT_RATE = 0.6
# Below this many comparable days, the field check is reported but not
# treated as pass/fail — not enough verified reports yet to be meaningful.
MIN_COMPARABLE_DAYS = 10

OVERVIEW_GROWTH_STAGE = "Tillering"


@dataclass
class StatisticalValidity:
    pest: str
    metrics: dict[str, float] | None
    passed: bool | None  # None = metrics file doesn't exist yet (model never trained)
    reasons: list[str] = field(default_factory=list)


@dataclass
class FieldValidity:
    pest: str
    compared_days: int
    agreeing_days: int
    agreement_rate: float | None
    passed: bool | None  # None = not enough comparable days to judge


def check_statistical_validity(pest: str) -> StatisticalValidity:
    from ml.config import PEST_PARAMS as params_map
    from app.decision.etl_thresholds import PEST_THRESHOLDS

    weights_path = params_map[pest].bilstm_weights_path
    metrics_path = weights_path.parent / f"bilstm_{pest.lower()}_test_metrics.json"

    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return StatisticalValidity(pest=pest, metrics=None, passed=None, reasons=["No test metrics file — model not trained yet."])

    reasons: list[str] = []
    passed = True

    if metrics["r2"] < MIN_R2:
        passed = False
        reasons.append(f"R2={metrics['r2']:.3f} < minimum {MIN_R2}")

    # Use the stricter (Reproductive) High-risk cutoff as the MAE yardstick,
    # since that's the tighter band the model needs to resolve correctly.
    high_min = min(band.high_min for band in PEST_THRESHOLDS[pest].values())
    mae_ceiling = high_min * MAX_MAE_FRACTION_OF_HIGH_MIN
    if metrics["mae"] > mae_ceiling:
        passed = False
        reasons.append(f"MAE={metrics['mae']:.3f} exceeds {MAX_MAE_FRACTION_OF_HIGH_MIN:.0%} of the High-risk cutoff ({mae_ceiling:.3f})")

    if not reasons:
        reasons.append("Within accepted R2 and MAE bounds.")

    return StatisticalValidity(pest=pest, metrics=metrics, passed=passed, reasons=reasons)


def check_field_validity(pest: str) -> FieldValidity:
    """Aggregates GET /api/inference/gap-analysis's per-municipality
    comparison across every municipality an LGU account exists for."""
    municipalities = {u.municipality for u in list_lgu_users()}

    compared_days = 0
    agreeing_days = 0
    for municipality in municipalities:
        result = infer_gap_analysis(municipality, pest, OVERVIEW_GROWTH_STAGE)
        if result.status != "ok":
            continue
        compared_days += result.compared_days
        agreeing_days += result.agreeing_days

    if compared_days < MIN_COMPARABLE_DAYS:
        return FieldValidity(
            pest=pest, compared_days=compared_days, agreeing_days=agreeing_days, agreement_rate=None, passed=None
        )

    rate = agreeing_days / compared_days
    return FieldValidity(
        pest=pest,
        compared_days=compared_days,
        agreeing_days=agreeing_days,
        agreement_rate=rate,
        passed=rate >= MIN_FIELD_AGREEMENT_RATE,
    )


def _verdict_str(passed: bool | None) -> str:
    if passed is None:
        return "INCONCLUSIVE"
    return "PASS" if passed else "FAIL"


def main() -> None:
    print(f"Validity test run — {date.today().isoformat()}\n")

    overall_pass = True
    for pest in PEST_PARAMS:
        print(f"=== {pest} ===")

        stat = check_statistical_validity(pest)
        print(f"Statistical validity: {_verdict_str(stat.passed)}")
        for reason in stat.reasons:
            print(f"  - {reason}")
        if stat.passed is False:
            overall_pass = False

        field_result = check_field_validity(pest)
        print(f"Field validity: {_verdict_str(field_result.passed)}")
        if field_result.agreement_rate is not None:
            print(
                f"  - {field_result.agreeing_days}/{field_result.compared_days} days agreed with "
                f"verified reports ({field_result.agreement_rate:.0%}), threshold {MIN_FIELD_AGREEMENT_RATE:.0%}"
            )
        else:
            print(
                f"  - Only {field_result.compared_days} comparable days on file "
                f"(need >= {MIN_COMPARABLE_DAYS}) — not enough verified reports yet to judge."
            )
        if field_result.passed is False:
            overall_pass = False

        print()

    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()

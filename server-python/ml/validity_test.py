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

  2. FIELD VALIDITY — the model's weather-only forecast compared against
     LGU-verified farmer reports, one report at a time, via the same
     GET /api/reports/{report_id}/gap-analysis the admin dashboard's
     "Analyze Gap" button calls. For each verified report, the model's risk
     level for the report's own date is compared against the ETL risk level
     of the technologist-confirmed value. This answers "does the model's
     Low/Medium/High call agree with what was actually observed in the
     field," which the statistical check alone cannot show — the test split
     is historical weather-derived ground truth, not independent real-world
     confirmation.

Neither check changes anything: this is read-only, the same as the
gap-analysis endpoint itself (see app/routers/inference.py's _run_forecast
docstring for why verified reports never feed back into a live prediction).
A failing verdict here is a signal to retrain or revisit the architecture,
not something this script acts on itself.

Needs the database up (docker compose up -d) and the BiLSTM weights present.
Exits non-zero when any check fails, so it can gate a retrain in CI.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.validity_test
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import date

from app.data import reports_store
from app.decision.etl_thresholds import derive_risk_level
from app.decision.pest_matching import derive_pest_code
from app.decision.report_anchor import anchor_from_report
from app.routers.reports import get_report_gap_analysis
from ml.config import GROWTH_STAGE_BUCKETS, PEST_PARAMS

# Acceptance thresholds. R2 close to 0 means "no better than predicting the
# mean," which is the real floor for a regression model to be worth deploying.
#
# Do NOT lower this to make a model pass. R2 is a harsh yardstick for a
# low-variance target — RSB's damage percentages sit near zero most of the
# year, so the denominator in 1 - SSres/SStot is small and even a useful model
# scores poorly. The defensible response to a low R2 is to report it, show the
# MAE-against-band-width check below (which measures what actually matters for
# an IPM decision: can the forecast resolve the Low/Medium/High boundary), and
# say plainly in the paper which target the model does and doesn't fit well.
MIN_R2 = 0.3
MAX_MAE_FRACTION_OF_HIGH_MIN = 0.5  # MAE must be well under the High-risk cutoff to be useful for ETL bucketing

# Field validity: the share of verified reports whose observed ETL risk level
# the model's own forecast for that date agreed with.
MIN_FIELD_AGREEMENT_RATE = 0.6
# Below this many comparable reports, the field check is reported but not
# treated as pass/fail — not enough verified reports yet to be meaningful.
MIN_COMPARABLE_REPORTS = 10


@dataclass
class StatisticalValidity:
    pest: str
    metrics: dict[str, float] | None
    passed: bool | None  # None = metrics file doesn't exist yet (model never trained)
    reasons: list[str] = field(default_factory=list)


@dataclass
class FieldValidity:
    pest: str
    compared_reports: int
    agreeing_reports: int
    agreement_rate: float | None
    passed: bool | None  # None = not enough comparable reports to judge


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
    """Walks every verified report for this pest and asks, per report: did the
    weather-only model put the report's own date in the same ETL band as the
    technologist-confirmed value did?

    Day 0 of GET /api/reports/{report_id}/gap-analysis is the model's forecast
    for the report date, so the comparison here is exactly the one the
    dashboard shows a technician — aggregated rather than read one report at a
    time. Reports the endpoint can't analyze (unverified, no usable value, no
    weather history that far back, model not loaded) are skipped, not counted
    as disagreements.
    """
    compared = 0
    agreeing = 0

    for record in reports_store.list_reports():
        if record.deleted_at is not None or record.status != "verified":
            continue
        if (record.pest_code or derive_pest_code(record.pest_type)) != pest:
            continue

        growth_stage = (
            record.crop_growth_stage if record.crop_growth_stage in GROWTH_STAGE_BUCKETS else "Tillering"
        )
        bucket = GROWTH_STAGE_BUCKETS[growth_stage]

        anchor = anchor_from_report(record, bucket)
        if anchor is None:
            continue

        try:
            analysis = get_report_gap_analysis(record.id)
        except Exception:  # noqa: BLE001 — missing coordinates/weather shouldn't abort the whole sweep
            continue
        if analysis.status != "ok" or not analysis.days:
            continue

        predicted_level = analysis.days[0].historical_risk_level
        if predicted_level is None:
            continue

        observed_level = derive_risk_level(pest, bucket, anchor.verified_value)
        compared += 1
        agreeing += int(predicted_level == observed_level)

    if compared < MIN_COMPARABLE_REPORTS:
        return FieldValidity(
            pest=pest,
            compared_reports=compared,
            agreeing_reports=agreeing,
            agreement_rate=None,
            passed=None,
        )

    rate = agreeing / compared
    return FieldValidity(
        pest=pest,
        compared_reports=compared,
        agreeing_reports=agreeing,
        agreement_rate=rate,
        passed=rate >= MIN_FIELD_AGREEMENT_RATE,
    )


def _per_band_recall(etl: dict) -> list[tuple[str, float, int]]:
    """(band, recall, support) from the saved confusion matrix — rows are the
    actual band, so recall is the diagonal over the row total."""
    labels = etl["confusion_matrix_labels"]
    matrix = etl["confusion_matrix"]
    out = []
    for i, level in enumerate(labels):
        support = sum(matrix[i])
        out.append((level, matrix[i][i] / support if support else 0.0, support))
    return out


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
        # Written by ml/bilstm/train.py alongside the regression metrics; shown
        # here so one command surfaces both halves of RQ1.1. Absent on metrics
        # files written before the ETL check existed — retrain to populate.
        etl = (stat.metrics or {}).get("etl_classification")
        if etl:
            print(
                f"  - ETL band agreement: accuracy={etl['accuracy']:.3f} "
                f"precision={etl['precision_macro']:.3f} "
                f"recall={etl['recall_macro']:.3f} f1={etl['f1_macro']:.3f} (macro)"
            )
            # Headline accuracy is dominated by the Low band, so per-band recall
            # is printed separately: an early-warning system that never predicts
            # High is useless no matter how high its accuracy reads.
            for level, recall, support in _per_band_recall(etl):
                flag = ""
                if support == 0:
                    flag = "  <- no test samples in this band; not evaluable"
                elif recall == 0.0:
                    flag = "  <- MISSES EVERY CASE IN THIS BAND"
                print(f"      {level:<7} recall={recall:.3f}  (n={support}){flag}")
        if stat.passed is False:
            overall_pass = False

        field_result = check_field_validity(pest)
        print(f"Field validity: {_verdict_str(field_result.passed)}")
        if field_result.agreement_rate is not None:
            print(
                f"  - {field_result.agreeing_reports}/{field_result.compared_reports} verified reports "
                f"landed in the model's predicted ETL band ({field_result.agreement_rate:.0%}), "
                f"threshold {MIN_FIELD_AGREEMENT_RATE:.0%}"
            )
        else:
            print(
                f"  - Only {field_result.compared_reports} comparable verified reports on file "
                f"(need >= {MIN_COMPARABLE_REPORTS}) — not enough to judge."
            )
        if field_result.passed is False:
            overall_pass = False

        print()

    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()

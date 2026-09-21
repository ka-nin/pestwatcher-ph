"""Post-hoc adjustment of a forecast using LGU-verified farmer sightings.

Kept separate from app/models/bilstm_model.py for the same reason
app/decision/etl_thresholds.py is: the model must never learn its own
definition of risk, and it must never be nudged by unverified, free-text
farmer input either. A sighting only ever reaches this module after an LGU
technician has reviewed it in admin-web and marked it "verified"
(PATCH /api/reports/{id}) — a pending or rejected report has zero effect on
what anyone sees. This module never touches bilstm_forecaster.predict();
it only adjusts the already ETL-bucketed Low/Medium/High level one tier up
when there's enough recent, corroborated ground truth for it.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from app.data.reports_store import list_verified_reports
from app.decision.etl_thresholds import GrowthStageBucket, derive_risk_level

RiskLevel = Literal["Low", "Medium", "High"]
RISK_ORDER: list[RiskLevel] = ["Low", "Medium", "High"]

# How far back a verified report still counts as "current" ground truth.
LOOKBACK_DAYS = 14

# A verified report's severity ("low"/"medium"/"high", set by the farmer,
# unchanged by verification) contributes this many points toward bumping
# the forecast. Corroborating reports stack — two verified "medium"
# sightings carry the same weight as one verified "high" sighting.
SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3}
BUMP_THRESHOLD = 3

# Reports store free-text pest_type (whatever the farmer picked in the
# mobile app's dropdown, e.g. "Brown Planthopper (Kayumangging Hanip)");
# forecasts key by the BiLSTM's pest code. Matched by substring since
# there's no shared enum between the two apps yet.
PEST_KEYWORDS: dict[str, list[str]] = {
    "BPH": ["brown planthopper", "kayumangging hanip"],
    "RSB": ["stem borer", "aksip", "atip"],
}


@dataclass(frozen=True)
class ReportSignal:
    verified_report_count: int
    weight: int
    # Highest technologist-confirmed count/damage value among the matching
    # reports gathered, in the pest's ETL units — None if no verified report
    # carried a numeric value. Used to floor the risk level via the ETL
    # table directly, independent of the weight-based bump below.
    verified_value_floor: float | None = None


def _matches_pest(pest_type: str, pest_code: str) -> bool:
    needle = pest_type.lower()
    return any(keyword in needle for keyword in PEST_KEYWORDS.get(pest_code, []))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def gather_signal(municipality: str, pest_code: str) -> ReportSignal:
    """Verified, recent, matching-pest reports for one municipality."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    count = 0
    weight = 0
    value_floor: float | None = None

    for record in list_verified_reports(municipality):
        if not _matches_pest(record.pest_type, pest_code):
            continue

        verified_at = _parse_timestamp(record.verified_at) or _parse_timestamp(record.submitted_at)
        if verified_at is None or verified_at < cutoff:
            continue

        count += 1
        weight += SEVERITY_WEIGHT.get(record.severity, 0)

        if record.verified_value is not None and (value_floor is None or record.verified_value > value_floor):
            value_floor = record.verified_value

    return ReportSignal(verified_report_count=count, weight=weight, verified_value_floor=value_floor)


def apply_adjustment(
    risk_level: RiskLevel,
    municipality: str,
    pest_code: str,
    growth_stage_bucket: GrowthStageBucket,
) -> tuple[RiskLevel, ReportSignal]:
    """Bumps `risk_level` one tier when verified, recent, matching-pest
    reports for this municipality clear BUMP_THRESHOLD, then floors the
    result against the ETL table using the highest technologist-confirmed
    numeric value among those same reports (if any). Never lowers a level
    either way — ground truth can only raise alarm, it can't override the
    model down."""
    signal = gather_signal(municipality, pest_code)
    level = risk_level

    if signal.weight >= BUMP_THRESHOLD and level in RISK_ORDER:
        idx = RISK_ORDER.index(level)
        level = RISK_ORDER[min(idx + 1, len(RISK_ORDER) - 1)]

    if signal.verified_value_floor is not None:
        floor_level = derive_risk_level(pest_code, growth_stage_bucket, signal.verified_value_floor)
        if RISK_ORDER.index(floor_level) > RISK_ORDER.index(level):
            level = floor_level

    return level, signal

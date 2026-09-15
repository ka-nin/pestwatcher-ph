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

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from app.config import get_settings

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


def _reports_file() -> Path:
    settings = get_settings()
    return Path(settings.upload_dir).parent / "reports.json"


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
    path = _reports_file()
    if not path.exists():
        return ReportSignal(verified_report_count=0, weight=0)

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    count = 0
    weight = 0

    for record in json.loads(path.read_text(encoding="utf-8")):
        if record.get("status") != "verified":
            continue
        if record.get("municipality") != municipality:
            continue
        if not _matches_pest(record.get("pest_type", ""), pest_code):
            continue

        verified_at = _parse_timestamp(record.get("verified_at")) or _parse_timestamp(record.get("submitted_at"))
        if verified_at is None or verified_at < cutoff:
            continue

        count += 1
        weight += SEVERITY_WEIGHT.get(record.get("severity"), 0)

    return ReportSignal(verified_report_count=count, weight=weight)


def apply_adjustment(risk_level: RiskLevel, municipality: str, pest_code: str) -> tuple[RiskLevel, ReportSignal]:
    """Bumps `risk_level` one tier when verified, recent, matching-pest
    reports for this municipality clear BUMP_THRESHOLD. Never bumps past
    High, and never lowers a level — ground truth can only raise alarm, it
    can't override the model down."""
    signal = gather_signal(municipality, pest_code)
    if signal.weight < BUMP_THRESHOLD or risk_level not in RISK_ORDER:
        return risk_level, signal

    idx = RISK_ORDER.index(risk_level)
    return RISK_ORDER[min(idx + 1, len(RISK_ORDER) - 1)], signal

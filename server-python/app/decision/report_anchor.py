"""Re-anchors a pest's forecast on the latest LGU-verified farmer report.

Replaces the old "bump the Low/Medium/High label" rule. The BiLSTM never
sees pest counts (it is weather-only), so a report can't be fed into it —
instead, once a report is verified, every number the model produces for that
municipality + pest is shifted by a fixed gap for the next ANCHOR_DAYS days:

    gap = verified report value - what the model predicted for the report day
    shifted forecast = model forecast + gap x weight   (never below 0)

The weight fades linearly from 1 on the report day to 0 on day ANCHOR_DAYS, so
the report day equals the report's number, its influence shrinks a little
each day, and the forecast glides back to the plain weather-driven curve with
no jump when the window ends. A newer verified report replaces the older one
and restarts the fade; with no report inside the window the forecast is pure
weather, unchanged. Note the fade returns to what the weather says, not
automatically to "Low". The Low/Medium/High label is then derived
from the shifted number by the normal ETL thresholds
(app/decision/etl_thresholds.py) — the label itself is never bumped.

Only reports whose pest_code matches are used, so a BPH report never moves
the RSB forecast (different units, different model).

Most farmers can't give an exact count, so a verified report with no number
still counts: its severity is turned into a value from the same fixed ETL
bands used for the label (see severity_value). A technician-confirmed number,
when there is one, always wins.
"""

from dataclasses import dataclass
from datetime import date, datetime

from app.data.reports_store import list_verified_reports
from app.decision.etl_thresholds import PEST_THRESHOLDS, GrowthStageBucket
from app.decision.pest_matching import derive_pest_code

# A report's influence fades linearly to zero over this many days.
ANCHOR_DAYS = 13


@dataclass(frozen=True)
class ReportAnchor:
    anchor_date: date
    verified_value: float
    # Matching verified reports on the anchor day (the highest value wins).
    verified_report_count: int


def severity_value(pest_code: str, bucket: GrowthStageBucket, severity: str) -> float | None:
    """A representative value, in the pest's ETL units, for a report that has
    a farmer-picked severity but no count: "high" = the start of the High
    band, "medium" = the middle of the Medium band, "low" = half of the Low
    limit — so a "high" report lands the forecast in High, and so on."""
    band = PEST_THRESHOLDS[pest_code][bucket]
    return {
        "high": band.high_min,
        "medium": (band.low_max + band.high_min) / 2,
        "low": band.low_max / 2,
    }.get(severity.lower())


def _report_date(verified_at: str | None, submitted_at: str | None) -> date | None:
    # Verified-at is when the system actually learned of the report; the
    # timestamps are ISO 8601 UTC, converted to the server's local day so it
    # lines up with date.today() used everywhere else in the forecast code.
    for raw in (verified_at, submitted_at):
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw).astimezone().date()
        except ValueError:
            continue
    return None


def find_anchor(
    municipality: str, pest_code: str, today: date, growth_stage_bucket: GrowthStageBucket
) -> ReportAnchor | None:
    best_date: date | None = None
    values_on_best_date: list[float] = []

    for record in list_verified_reports(municipality):
        if (record.pest_code or derive_pest_code(record.pest_type)) != pest_code:
            continue
        value = record.verified_value
        if value is None:
            value = severity_value(pest_code, growth_stage_bucket, record.severity)
        if value is None:
            continue

        report_date = _report_date(record.verified_at, record.submitted_at)
        if report_date is None:
            continue
        age_days = (today - report_date).days
        if age_days < 0 or age_days >= ANCHOR_DAYS:
            continue

        if best_date is None or report_date > best_date:
            best_date = report_date
            values_on_best_date = [value]
        elif report_date == best_date:
            values_on_best_date.append(value)

    if best_date is None:
        return None
    return ReportAnchor(
        anchor_date=best_date,
        verified_value=max(values_on_best_date),
        verified_report_count=len(values_on_best_date),
    )


def weight(anchor: ReportAnchor, target_date: date) -> float:
    """1.0 on the report day, falling evenly to 0.0 at ANCHOR_DAYS; 0.0 for
    any date before the report or past the window."""
    days_after = (target_date - anchor.anchor_date).days
    if days_after < 0 or days_after >= ANCHOR_DAYS:
        return 0.0
    return 1.0 - days_after / ANCHOR_DAYS


def shifted(predicted_value: float, gap: float, weight_on_day: float) -> float:
    return max(0.0, predicted_value + gap * weight_on_day)

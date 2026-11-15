"""How fast a pest is projected to grow, and how far it has spread.

The 2026-10 panel asked the system to say not only whether a pest is present
but "gaano kabilis dumami, gaano kalawak": how quickly it increases and how
far it spreads. Two separate summaries, because they come from different
evidence:

  growth_outlook  read off the BiLSTM's own 14-day trajectory: direction,
                  projected change per day, doubling time while rising, and
                  how many days until the forecast first reaches High. This
                  is a description of the forecast, so it is only as good
                  as the forecast; it never adds information of its own.

  spread_summary  read off technologist-verified reports: hectares reported
                  affected in the last SPREAD_WINDOW_DAYS against the
                  window before, plus the average photo-estimated coverage.
                  This is OBSERVED extent, not a forecast of future spread:
                  forecasting spread would need extent measured over time
                  (e.g. repeated field or drone imagery), which the system
                  doesn't have yet.

Both are deliberately simple rules, like app/decision/etl_thresholds.py, so
every number on screen traces back to a stated calculation.
"""

import math
from datetime import date, timedelta

from app.data.reports_store import list_verified_reports
from app.decision.pest_matching import derive_pest_code

# Below these, "percent change" is meaningless (any change from ~0 is
# infinite percent), so relative growth and doubling time are not reported.
RELATIVE_FLOOR = {"BPH": 0.5, "RSB": 0.1}
# A total change smaller than this over the trajectory reads as "stable".
STABLE_TOLERANCE = {"BPH": 0.5, "RSB": 0.1}
MAX_DOUBLING_DAYS = 60  # slower than this isn't a useful warning
SPREAD_WINDOW_DAYS = 30


def growth_outlook(points: list, pest: str) -> dict | None:
    """`points` are TrajectoryPoint-like objects in date order, starting today."""
    if len(points) < 2:
        return None

    values = [p.predicted_value for p in points]
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    slope = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values)) / sum((i - x_mean) ** 2 for i in range(n))

    start, end = values[0], values[-1]
    change = end - start
    if abs(change) < STABLE_TOLERANCE[pest]:
        trend = "stable"
    else:
        trend = "rising" if change > 0 else "falling"

    pct_per_day = None
    doubling_days = None
    if start >= RELATIVE_FLOOR[pest] and end > 0:
        rate = (end / start) ** (1 / (n - 1)) - 1
        pct_per_day = rate * 100
        if rate > 0:
            doubling = math.log(2) / math.log(1 + rate)
            doubling_days = round(doubling, 1) if doubling <= MAX_DOUBLING_DAYS else None

    days_to_high = next((i for i, p in enumerate(points) if p.risk_level == "High"), None)
    peak_index = max(range(n), key=lambda i: values[i])

    return {
        "trend": trend,
        "change_per_day": round(slope, 3),
        "pct_change_per_day": round(pct_per_day, 1) if pct_per_day is not None else None,
        "doubling_days": doubling_days,
        "days_to_high": days_to_high,
        "peak_value": round(values[peak_index], 2),
        "peak_date": points[peak_index].date,
        "days_covered": n,
    }


def _report_day(record) -> date | None:
    for value in (record.date_spotted, (record.verified_at or "")[:10], (record.submitted_at or "")[:10]):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            continue
    return None


def spread_summary(municipality: str, pest: str, today: date) -> dict:
    """Observed extent from verified reports for one municipality + pest."""
    recent_start = today - timedelta(days=SPREAD_WINDOW_DAYS)
    previous_start = recent_start - timedelta(days=SPREAD_WINDOW_DAYS)

    recent_area = previous_area = 0.0
    recent_reports = previous_reports = 0
    coverages: list[float] = []

    for record in list_verified_reports(municipality):
        if (record.pest_code or derive_pest_code(record.pest_type)) != pest:
            continue
        day = _report_day(record)
        if day is None or day > today:
            continue
        area = record.area_affected or 0.0
        if day > recent_start:
            recent_reports += 1
            recent_area += area
            if record.ai_suggested_coverage_pct is not None:
                coverages.append(record.ai_suggested_coverage_pct)
        elif day > previous_start:
            previous_reports += 1
            previous_area += area

    if recent_reports == 0 and previous_reports == 0:
        trend = None
    elif recent_area > previous_area * 1.1:
        trend = "spreading"
    elif recent_area < previous_area * 0.9:
        trend = "shrinking"
    else:
        trend = "steady"

    return {
        "window_days": SPREAD_WINDOW_DAYS,
        "recent_reports": recent_reports,
        "recent_hectares": round(recent_area, 2),
        "previous_reports": previous_reports,
        "previous_hectares": round(previous_area, 2),
        "trend": trend,
        "mean_photo_coverage_pct": round(sum(coverages) / len(coverages), 1) if coverages else None,
    }


# Guardrail on the projections below: with no field size on record, a forecast
# that jumps from 0.5 to 20 would otherwise imply a 40x larger affected area.
MAX_AREA_GROWTH_FACTOR = 5.0


def project_by_forecast_ratio(
    points: list, anchor: float | None, max_growth_factor: float = MAX_AREA_GROWTH_FACTOR, round_digits: int = 2
) -> list[float | None]:
    """Per-day projection of any quantity anchored to day 0, one entry per
    trajectory point: value(day) = anchor * forecast(day) / forecast(day 0),
    capped so a small/noisy anchor forecast ratio can't blow up the far end
    of the trajectory.

    A PROJECTION under one stated assumption, not a measured or learned
    growth curve: the anchored quantity is taken to grow in proportion to
    the forecast pest level, because that is the only signal this system
    has connecting "today" to "day N" — there is no training data for how
    fast visible field damage (severity %, spread %, affected area) grows
    day to day. Used for affected hectares (verified-report anchor) and,
    for a single field-assessment photo, its own severity/spread/area
    readings (POST /field-assessment) — same math, different anchor.

    `round_digits` defaults to 2 (fine for a percentage 0-100), but hectares
    callers should pass more — a small test plot (0.01 ha) at a low severity %
    easily works out to a true affected area under 0.0001 ha, which 2 decimals
    would round away to a misleading 0.0 even though it's a real, nonzero
    number of square metres once converted back for display.

    With no anchor on record (or a zero/negative forecast to scale from)
    there is nothing to project from, so every entry is None.
    """
    if not points or anchor is None or anchor <= 0:
        return [None] * len(points)
    base = points[0].predicted_value
    if base <= 0:
        return [None] * len(points)
    return [
        round(anchor * min(max(p.predicted_value / base, 0.0), max_growth_factor), round_digits)
        for p in points
    ]


def project_affected_area(points: list, anchor_hectares: float | None) -> list[float | None]:
    """Per-day projected affected hectares, one entry per trajectory point —
    see project_by_forecast_ratio for the shared projection method. Day 0
    equals the verified-report area (the anchor)."""
    return project_by_forecast_ratio(points, anchor_hectares, round_digits=6)

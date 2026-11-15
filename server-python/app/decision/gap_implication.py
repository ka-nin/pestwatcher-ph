"""Turns a gap analysis (see app/schemas/inference.py's GapAnalysisDay and
GapAnalysisResponse) into a short plain-language reading a technician can
use without doing the comparison themselves.

Two separate statements, because they answer different questions:

  1. The gap itself: the field value the technologist verified vs. what the
     model forecast for that date WITHOUT any report (the historical line).
     This is how wrong the weather-and-growth-stage forecast was.
  2. The system's response: how much the deployed model's forecast changes
     once this report is fed in as its verified-observation input (the
     report-based line). This is how far the report actually moves what
     farmers are shown.

Deliberately simple and rule-based, not learned, in the same spirit as
app/decision/etl_thresholds.py: an implication should be traceable to a
fixed rule, not a model's own judgment call.
"""

from app.schemas.inference import GapAnalysisDay

RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}


def describe_gap(
    days: list[GapAnalysisDay],
    pest: str,
    verified_risk_level: str | None,
    report_is_model_input: bool,
) -> str:
    """`days` must be in chronological order, starting on the report's own
    date (see app/routers/reports.py's gap-analysis endpoint)."""
    if not days:
        return "No comparable days — the weather history needed for this window isn't available yet."

    first = days[0]
    if first.historical_risk_level is None or verified_risk_level is None:
        return "Not enough weather history to compute a forecast for this report's date."

    # ---- 1. field vs. the forecast made without the report
    predicted, observed = first.historical_risk_level, verified_risk_level
    if RISK_RANK[observed] == RISK_RANK[predicted]:
        gap = (
            f"The field report agrees with the model: without any report it forecast {predicted} risk "
            f"for {pest} on this date, and the technologist verified {observed}."
        )
    else:
        direction = "higher" if RISK_RANK[observed] > RISK_RANK[predicted] else "lower"
        severity = "much" if abs(RISK_RANK[observed] - RISK_RANK[predicted]) >= 2 else "somewhat"
        reading = (
            "the model may be underestimating this outbreak"
            if direction == "higher"
            else "the model may be overestimating risk here"
        )
        gap = (
            f"The field was {severity} {direction} than forecast: without any report the model called "
            f"{predicted} risk, but the technologist verified {observed}, so {reading}."
        )

    # ---- 2. how far the report moves the deployed forecast
    if not report_is_model_input:
        return gap + " The deployed model does not take verified reports as an input, so this report does not change the forecast."

    comparable = [
        d for d in days if d.historical_risk_level is not None and d.report_based_risk_level is not None
    ]
    changed_days = sum(1 for d in comparable if d.historical_risk_level != d.report_based_risk_level)
    shift = (
        first.report_based_value - first.historical_value
        if first.report_based_value is not None and first.historical_value is not None
        else None
    )

    if changed_days == 0:
        response = (
            f" With this report as an input, the forecast stays at the same risk level on all "
            f"{len(comparable)} days"
        )
        response += f" (it moves by {shift:+.1f} on the report's date)." if shift is not None else "."
        if RISK_RANK[observed] != RISK_RANK[predicted]:
            response += " The report is recorded, but it is not enough on its own to change what farmers are shown."
    else:
        response = (
            f" With this report as an input, the forecast's risk level changes on {changed_days} of "
            f"{len(comparable)} days"
            + (f", starting at {first.report_based_risk_level} on the report's date." if first.report_based_risk_level else ".")
        )

    return gap + response

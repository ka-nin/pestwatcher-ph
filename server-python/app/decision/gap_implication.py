"""Turns a gap analysis's two 14-day trajectories (historical vs.
report-based — see app/schemas/inference.py's GapAnalysisDay) into one
plain-language sentence a technician can read without doing the comparison
themselves.

Deliberately simple and rule-based, not learned — same spirit as
app/decision/etl_thresholds.py: an implication should be traceable to a
fixed rule, not a model's own judgment call.
"""

from app.schemas.inference import GapAnalysisDay

RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}


def describe_gap(days: list[GapAnalysisDay], pest: str) -> str:
    """`days` must be in chronological order, starting on the report's own
    date (see app/routers/reports.py's gap-analysis endpoint)."""
    if not days:
        return "No comparable days — the weather history needed for this window isn't available yet."

    anchor_day = days[0]
    if anchor_day.historical_risk_level is None or anchor_day.report_based_risk_level is None:
        return "Not enough weather history to compute a forecast for this report's date."

    historical_rank = RISK_RANK[anchor_day.historical_risk_level]
    report_rank = RISK_RANK[anchor_day.report_based_risk_level]

    if report_rank == historical_rank:
        return (
            f"The report confirms the model: weather alone already predicted "
            f"{anchor_day.historical_risk_level} risk for {pest} on this date, matching what was verified "
            f"in the field."
        )

    direction = "higher" if report_rank > historical_rank else "lower"
    magnitude = abs(report_rank - historical_rank)
    severity_word = "sharply" if magnitude >= 2 else "somewhat"

    # How many of the following days still show a gap between the two
    # trajectories, as a rough sense of how long the discrepancy lingers —
    # mirrors the same fading window report_anchor.py uses, just read back
    # out of the two already-computed series instead of recomputed here.
    lingering_days = sum(
        1
        for d in days[1:]
        if d.historical_risk_level is not None
        and d.report_based_risk_level is not None
        and d.historical_risk_level != d.report_based_risk_level
    )

    base = (
        f"The verified report was {severity_word} {direction} than what weather alone predicted: "
        f"the model's weather-only forecast called {anchor_day.historical_risk_level} risk, but the field "
        f"report puts it at {anchor_day.report_based_risk_level}."
    )

    if direction == "higher":
        implication = (
            " This suggests the model may be underestimating this outbreak — weather conditions alone "
            "didn't fully capture what's happening in the field."
        )
    else:
        implication = (
            " This suggests the model may be overestimating risk here — the field report found less "
            "pest pressure than the weather-driven forecast expected."
        )

    trailing = (
        f" The gap is expected to narrow over the next {lingering_days} day(s) as the report's influence fades."
        if lingering_days
        else " The two forecasts converge again within a day or two."
    )

    return base + implication + trailing

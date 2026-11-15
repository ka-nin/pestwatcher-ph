"""Severity against spread, from real verified field reports.

The panel asked how severe an infestation is AND how widely it has spread.
This plots exactly those two quantities for every technologist-verified report:
x = severity (hoppers per hill for BPH, % damage for RSB), y = hectares the
report says are affected. One point per report, real data, no model output.

A point is FILLED when the severity is a number (the technologist's verified
value, else the farmer's estimate) and HOLLOW when it was only a Low/Medium/High
label that has been converted to a representative value from the ETL bands
(app/decision/report_anchor.py's severity_value), because most farmers give no
count. Colour is the severity label. Reports without an area are left out and
counted in the title: no area, no spread.

Two steps because the database driver and matplotlib live in different Python
environments:

  1. Export (server venv, needs the database; point DATABASE_URL at the field
     database to use the real reports):
         .venv/bin/python -m ml.analysis.severity_spread_scatter export
  2. Plot (any Python with pandas, scipy and matplotlib):
         PYTHONPATH=. python -m ml.analysis.severity_spread_scatter plot

Output: ml/analysis/figures/severity_vs_spread.png and severity_vs_spread_reports.csv
"""

import csv
import sys
from pathlib import Path

FIG_DIR = Path(__file__).resolve().parent / "figures"
CSV_PATH = FIG_DIR / "severity_vs_spread_reports.csv"
FIELDS = ["id", "pest", "municipality", "date", "severity", "value", "value_source", "area_ha"]


def export() -> None:
    from app.db import session_scope
    from app.db_models import ReportDB
    from app.decision.etl_thresholds import PEST_THRESHOLDS  # noqa: F401  (import check)
    from app.decision.pest_matching import derive_pest_code
    from app.decision.report_anchor import severity_value
    from ml.config import GROWTH_STAGE_BUCKETS

    rows = []
    with session_scope() as db:
        for r in db.query(ReportDB).filter(ReportDB.status == "verified", ReportDB.deleted_at.is_(None)).all():
            pest = r.pest_code or derive_pest_code(r.pest_type)
            if pest not in ("BPH", "RSB"):
                continue
            value = r.verified_value if r.verified_value is not None else r.estimated_value
            source = "numeric"
            if value is None:
                bucket = GROWTH_STAGE_BUCKETS.get(r.crop_growth_stage, "Vegetative")
                value, source = severity_value(pest, bucket, r.severity), "severity-band"
            rows.append({
                "id": r.id, "pest": pest, "municipality": r.municipality,
                "date": (r.date_spotted or "")[:10], "severity": (r.severity or "").lower(),
                "value": "" if value is None else round(value, 2), "value_source": source,
                "area_ha": "" if r.area_affected is None else r.area_affected,
            })
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with_area = sum(1 for r in rows if r["area_ha"] != "")
    print(f"exported {len(rows)} verified BPH/RSB reports, {with_area} with an area -> {CSV_PATH}")


def plot() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from scipy.stats import spearmanr

    df = pd.read_csv(CSV_PATH)
    colours = {"low": "#4c9f50", "medium": "#e0a21b", "high": "#c0392b"}
    units = {"BPH": "Severity (hoppers per hill)", "RSB": "Severity (% damage)"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, pest in zip(axes, ("BPH", "RSB")):
        sub = df[df.pest == pest]
        plotted = sub.dropna(subset=["value", "area_ha"])
        for _, r in plotted.iterrows():
            c = colours.get(r.severity, "#777777")
            hollow = r.value_source != "numeric"
            ax.scatter(r.value, r.area_ha, s=70, facecolors="none" if hollow else c, edgecolors=c, linewidths=1.8, zorder=3)
        ax.set_xlabel(units[pest])
        ax.set_ylabel("Area affected (hectares)")
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.25)
        n, skipped = len(plotted), len(sub) - len(plotted)
        title = f"{'Brown planthopper' if pest == 'BPH' else 'Rice stem borer'}: n = {n}"
        if skipped:
            title += f" ({skipped} verified reports have no area)"
        ax.set_title(title, fontsize=10)
        if n >= 5 and plotted.value.nunique() > 1 and plotted.area_ha.nunique() > 1:
            rho, p = spearmanr(plotted.value, plotted.area_ha)
            ax.annotate(f"Spearman ρ = {rho:+.2f}  (p = {p:.2f})", (0.03, 0.94), xycoords="axes fraction", fontsize=9)
        else:
            ax.annotate("too few reports with an area to show a trend", (0.5, 0.5), xycoords="axes fraction",
                        ha="center", fontsize=9, color="#888888")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=k.capitalize()) for k, c in colours.items()]
    handles += [plt.Line2D([], [], marker="o", ls="", mfc="none", color="#555555", label="severity from Low/Medium/High label"),
                plt.Line2D([], [], marker="o", ls="", color="#555555", label="severity is a number")]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("Severity vs spread: technologist-verified field reports", fontweight="bold")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    out = FIG_DIR / "severity_vs_spread.png"
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    {"export": export, "plot": plot}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()

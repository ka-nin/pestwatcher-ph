"""Folds LGU-verified farmer reports into the BiLSTM's training data, for
periodic retraining (monthly, or sooner once enough new reports have
accumulated — see this module's module-level docstring further down for the
trigger rule).

This is the "continuous learning" seam: verified reports never change a
live forecast (see app/routers/inference.py's _run_forecast docstring —
that adjustment was removed), but they DO become next month's ground truth,
the same way the original historical dataset did. Running this script and
then rerunning build_sequences.py + train.py is how a report actually
affects the system — through the next trained model, not through today's
prediction.

Output: ml/datasets/processed/weather_pest_daily_from_reports.csv, in the
exact same schema as CLEAN_DAILY_CSV (ml/config.py) — Region/Province/
Municipality/Date/weather columns/Rice_Growth_Stage/pest columns — so
build_sequences.py's load_clean_daily() can concatenate the two before
windowing. This file is REGENERATED FROM SCRATCH on every run (all verified
reports to date, re-fetched), not appended to — safe to delete and rerun.

A single verified report only tells us about ONE pest on ONE day; the
other pest's column for that row is left NaN. build_sequences.py's
groupby-municipality windowing already tolerates gaps (a report-derived row
without a full CRF_WINDOW_DAYS run of neighboring days simply can't anchor
a window, so it's skipped, not an error) — see build_sequences_for_pest's
`last_start` bound, which only ever looks at a municipality's own
contiguous rows.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.ingest_reports

Retrain trigger (manual runbook, no scheduler exists in this repo — see
server-python/README.md's deployment-infra notes): run this + build_sequences
+ train monthly, OR immediately once REPORT_COUNT_THRESHOLD new verified
reports have landed since the last run, whichever comes first. The
threshold exists so a sudden cluster of verified sightings (e.g. an actual
outbreak) doesn't sit unused for weeks waiting on the calendar.
"""

import sys
from datetime import date, datetime

import numpy as np
import pandas as pd

from app.data.municipalities import municipality_coordinates
from app.data.reports_store import list_reports
from app.decision.pest_matching import derive_pest_code
from app.routers.weather import fetch_archive_daily_weather_range
from app.schemas.reports import ReportRecord
from ml.config import PEST_PARAMS, PROCESSED_DATA_DIR

OUTPUT_CSV = PROCESSED_DATA_DIR / "weather_pest_daily_from_reports.csv"

# See this module's docstring for how the two trigger conditions combine.
REPORT_COUNT_THRESHOLD = 25

CSV_COLUMNS = [
    "Region",
    "Province",
    "Municipality",
    "Date",
    "Tmin",
    "Tmax",
    "Relative_Humidity",
    "Rainfall",
    "Dew_Point",
    "Solar_Radiation",
    "Rice_Growth_Stage",
    "BPH_Hoppers_per_Hill",
    "RSB_Dead_Hearts_Pct",
    "RSB_White_Ears_Pct",
]


def _verified_value(record: ReportRecord) -> float | None:
    """A verified report's ground-truth number — the technician-confirmed
    count/damage if there is one, else the farmer's own estimate. Mirrors
    app/decision/report_anchor.py's numeric-value preference, minus the
    severity-word fallback (a free-text "high"/"medium"/"low" isn't precise
    enough to use as a training label; only reports with a real number are
    worth ingesting here)."""
    return record.verified_value if record.verified_value is not None else record.estimated_value


def _report_date(record: ReportRecord) -> date | None:
    raw = record.verified_at or record.submitted_at
    try:
        return datetime.fromisoformat(raw).astimezone().date()
    except (ValueError, TypeError):
        return None


def fetch_archive_daily_weather(latitude: float, longitude: float, target: date) -> dict | None:
    """One day of ERA5 reanalysis weather for `target`, via the shared
    range-fetch helper (app/routers/weather.py) — same dataset
    CLEAN_DAILY_CSV's original historical rows came from. None if the
    archive has no data for that day (also used by
    GET /api/reports/{report_id}/gap-analysis, which fetches a whole range
    at once rather than one day per call — this single-day wrapper exists
    only because build_rows() below looks up one (municipality, date) pair
    at a time from a cache keyed the same way)."""
    days = fetch_archive_daily_weather_range(latitude, longitude, target, target)
    if not days:
        return None
    day = days[0]
    return {k: v for k, v in day.items() if k != "date"}


def build_rows() -> tuple[pd.DataFrame, int]:
    """One row per (municipality, date) that has at least one usable
    verified report — both pests' reports for the same municipality+date
    are merged into a single row rather than producing two partial rows."""
    all_reports = list_reports()
    verified = [r for r in all_reports if r.status == "verified"]

    # (municipality, date) -> accumulated row fields
    rows: dict[tuple[str, date], dict] = {}
    weather_cache: dict[tuple[str, date], dict | None] = {}

    for record in verified:
        value = _verified_value(record)
        if value is None:
            continue
        report_date = _report_date(record)
        if report_date is None:
            continue
        pest_code = record.pest_code or derive_pest_code(record.pest_type)
        if pest_code not in PEST_PARAMS:
            continue

        coordinates = municipality_coordinates(record.municipality)
        if coordinates is None:
            continue
        latitude, longitude = coordinates

        key = (record.municipality, report_date)
        if key not in weather_cache:
            weather_cache[key] = fetch_archive_daily_weather(latitude, longitude, report_date)
        weather = weather_cache[key]
        if weather is None:
            continue

        row = rows.setdefault(
            key,
            {
                "Region": "",
                "Province": record.province,
                "Municipality": record.municipality,
                "Date": report_date.isoformat(),
                "Tmin": weather["tmin"],
                "Tmax": weather["tmax"],
                "Relative_Humidity": weather["relative_humidity"],
                "Rainfall": weather["rainfall"],
                "Dew_Point": np.nan,
                "Solar_Radiation": np.nan,
                "Rice_Growth_Stage": record.crop_growth_stage,
                "BPH_Hoppers_per_Hill": np.nan,
                "RSB_Dead_Hearts_Pct": np.nan,
                "RSB_White_Ears_Pct": np.nan,
            },
        )

        if pest_code == "BPH":
            row["BPH_Hoppers_per_Hill"] = value
        elif pest_code == "RSB":
            # Same stage-bucket split build_sequences.py's RSB_TARGET_BY_STAGE_BUCKET
            # uses — a verified RSB report's number only means one of the two
            # damage indicators, depending on the report's own growth stage.
            from ml.config import GROWTH_STAGE_BUCKETS

            bucket = GROWTH_STAGE_BUCKETS.get(record.crop_growth_stage, "Vegetative")
            if bucket == "Reproductive":
                row["RSB_White_Ears_Pct"] = value
            else:
                row["RSB_Dead_Hearts_Pct"] = value

    df = pd.DataFrame(rows.values(), columns=CSV_COLUMNS)
    return df, len(verified)


def main() -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df, verified_count = build_rows()

    if df.empty:
        print("No verified reports with a usable numeric value yet — nothing written.")
        return

    df = df.sort_values(["Municipality", "Date"]).reset_index(drop=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {len(df)} report-derived daily rows ({verified_count} verified reports considered) -> {OUTPUT_CSV}")
    if verified_count >= REPORT_COUNT_THRESHOLD:
        print(
            f"NOTE: {verified_count} verified reports on file >= threshold ({REPORT_COUNT_THRESHOLD}) — "
            "per this module's retrain-trigger rule, retrain now rather than waiting for next month."
        )


if __name__ == "__main__":
    sys.exit(main())

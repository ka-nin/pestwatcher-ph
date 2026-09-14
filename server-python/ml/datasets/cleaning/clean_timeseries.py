"""Cleans ml/datasets/raw/weather_raw.csv and pest_raw.csv, then merges them
into a single daily (Municipality, Date) series in ml/datasets/processed/.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.datasets.cleaning.clean_timeseries

This does NOT compute GDD/CRF/HP or any other engineered feature — that
happens later in ml/bilstm/build_sequences.py, using ml/config.py for the
per-pest parameters (T_base, window sizes, RH threshold). This script only
gets the raw series into a trustworthy state: no duplicates, no impossible
sensor readings, no missing values, consistent categorical labels.

Every correction below is counted and written to
processed/cleaning_report.json so the counts can be cited directly in the
thesis's data cleaning methodology section.
"""

import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "processed"

VALID_GROWTH_STAGES = [
    "Seedling",
    "Tillering",
    "Elongation",
    "Panicle",
    "Flowering",
    "Ripening",
]

JOIN_KEYS = ["Region", "Province", "Municipality", "Date"]
WEATHER_NUMERIC_COLS = [
    "Tmin",
    "Tmax",
    "Relative_Humidity",
    "Rainfall",
    "Dew_Point",
    "Solar_Radiation",
]
PEST_NUMERIC_COLS = [
    "BPH_Hoppers_per_Hill",
    "RSB_Dead_Hearts_Pct",
    "RSB_White_Ears_Pct",
]


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    weather = pd.read_csv(RAW_DIR / "weather_raw.csv", parse_dates=["Date"])
    pest = pd.read_csv(RAW_DIR / "pest_raw.csv", parse_dates=["Date"])
    return weather, pest


def drop_exact_duplicates(df: pd.DataFrame, report: dict, name: str) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    report[f"{name}_exact_duplicates_dropped"] = before - len(df)
    return df


def standardize_growth_stage(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    original = df["Rice_Growth_Stage"]
    cleaned = original.str.strip().str.title()
    changed = (cleaned != original).sum()
    report["growth_stage_labels_normalized"] = int(changed)

    unknown = ~cleaned.isin(VALID_GROWTH_STAGES)
    report["growth_stage_unrecognized_after_cleanup"] = int(unknown.sum())
    if unknown.any():
        df = df.loc[~unknown].copy()

    df["Rice_Growth_Stage"] = cleaned.loc[df.index]
    return df


def null_out_impossible_weather_values(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    df = df.copy()

    tmin_gt_tmax = df["Tmin"] > df["Tmax"]
    df.loc[tmin_gt_tmax, ["Tmin", "Tmax"]] = pd.NA
    report["weather_tmin_gt_tmax_rows_nulled"] = int(tmin_gt_tmax.sum())

    rh_out_of_range = (df["Relative_Humidity"] > 100) | (df["Relative_Humidity"] < 0)
    df.loc[rh_out_of_range, "Relative_Humidity"] = pd.NA
    report["weather_rh_out_of_range_nulled"] = int(rh_out_of_range.sum())

    negative_rainfall = df["Rainfall"] < 0
    df.loc[negative_rainfall, "Rainfall"] = pd.NA
    report["weather_negative_rainfall_nulled"] = int(negative_rainfall.sum())

    return df


def clip_impossible_pest_values(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    df = df.copy()

    negative_bph = df["BPH_Hoppers_per_Hill"] < 0
    df.loc[negative_bph, "BPH_Hoppers_per_Hill"] = pd.NA
    report["pest_negative_bph_nulled"] = int(negative_bph.sum())

    for col in ["RSB_Dead_Hearts_Pct", "RSB_White_Ears_Pct"]:
        out_of_range = (df[col] < 0) | (df[col] > 100)
        df.loc[out_of_range, col] = pd.NA
        report[f"pest_{col.lower()}_out_of_range_nulled"] = int(out_of_range.sum())

    return df


def interpolate_missing(df: pd.DataFrame, cols: list[str], report: dict, name: str) -> pd.DataFrame:
    """Fills gaps per municipality along the date axis. Interior gaps are
    linearly interpolated (a station being briefly offline); any gap at the
    very start/end of a municipality's series is filled from the nearest
    known value, since interpolation can't extrapolate beyond the data.
    """
    df = df.sort_values(["Municipality", "Date"]).copy()
    before_missing = df[cols].isna().sum().sum()

    df[cols] = df.groupby("Municipality")[cols].transform(
        lambda s: s.interpolate(method="linear", limit_direction="both")
    )

    after_missing = df[cols].isna().sum().sum()
    report[f"{name}_missing_values_interpolated"] = int(before_missing - after_missing)
    report[f"{name}_missing_values_remaining"] = int(after_missing)
    return df


def main() -> None:
    report: dict = {}

    weather, pest = load_raw()

    weather = drop_exact_duplicates(weather, report, "weather")
    pest = drop_exact_duplicates(pest, report, "pest")

    pest = standardize_growth_stage(pest, report)

    weather = null_out_impossible_weather_values(weather, report)
    pest = clip_impossible_pest_values(pest, report)

    weather = interpolate_missing(weather, WEATHER_NUMERIC_COLS, report, "weather")
    pest = interpolate_missing(pest, PEST_NUMERIC_COLS, report, "pest")

    # BPH is a discrete count; interpolation produces fractional values that
    # need rounding back to whole hoppers/hill after the fill.
    pest["BPH_Hoppers_per_Hill"] = pest["BPH_Hoppers_per_Hill"].round().astype(int)

    merged = pd.merge(weather, pest, on=JOIN_KEYS, how="inner")
    report["weather_rows"] = len(weather)
    report["pest_rows"] = len(pest)
    report["merged_rows"] = len(merged)
    report["weather_rows_unmatched"] = len(weather) - len(merged)
    report["pest_rows_unmatched"] = len(pest) - len(merged)

    merged = merged.sort_values(["Municipality", "Date"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / "weather_pest_daily_clean.csv"
    merged.to_csv(output_path, index=False)

    report_path = PROCESSED_DIR / "cleaning_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"Wrote {len(merged)} rows to {output_path}")
    print(f"Cleaning report written to {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

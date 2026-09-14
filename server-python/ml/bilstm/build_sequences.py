"""Turns the cleaned daily weather+pest series into windowed sequences for
the BiLSTM outbreak forecaster.

For each pest (BPH, RSB) and each municipality, builds sliding windows of
CRF_WINDOW_DAYS consecutive days, paired with the pest's regression target
FORECAST_HORIZON_DAYS after the window ends. This is what the panel's
regression fix (fix #1) requires: the model is trained to predict a
continuous value, not a pre-bucketed risk class.

Each window produces two feature groups, not one:
  - a per-day sequence (Tmax, Tmin, RH, Rainfall, daily VPD, daily diurnal
    range, that day's growth-stage one-hot) — genuinely time-varying, so the
    LSTM has real temporal signal to learn from
  - a static aggregate vector (GDD accumulated, CRF, HP, WSI, rainfall/temp
    trend, growth-stage interaction terms) computed once over the whole
    window — these summarize the window rather than vary within it, so they
    are meant to be concatenated with the LSTM's output rather than fed at
    every timestep

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.build_sequences

Output: one .npz per pest in ml/datasets/processed/sequences/, holding
X_sequence (num_samples, window_days, num_seq_features), X_static
(num_samples, num_static_features), y (num_samples,), and both feature
column orders — plus a matching metadata CSV (municipality, window
start/end date, target date) so a prediction can be traced back to its
source rows.
"""

import json

import numpy as np
import pandas as pd

from app.preprocessing.features import (
    calculate_crf,
    calculate_diurnal_range,
    calculate_gdd,
    calculate_hp,
    calculate_trend,
    calculate_vpd,
    calculate_wsi,
)
from ml.config import (
    CLEAN_DAILY_CSV,
    FORECAST_HORIZON_DAYS,
    GROWTH_STAGE_BUCKETS,
    PEST_PARAMS,
    SEQUENCES_DIR,
)

GROWTH_STAGES = ["Seedling", "Tillering", "Elongation", "Panicle", "Flowering", "Ripening"]

SEQUENCE_FEATURE_COLUMNS = [
    "Tmax",
    "Tmin",
    "Relative_Humidity",
    "Rainfall",
    "vpd_daily",
    "diurnal_range_daily",
    *[f"growth_stage_{stage.lower()}" for stage in GROWTH_STAGES],
]

STATIC_FEATURE_COLUMNS = [
    "gdd_accum",
    "crf",
    "hp",
    "wsi",
    "rainfall_trend",
    "temp_trend",
    "is_reproductive_target",
    "reproductive_x_rainfall",
    "reproductive_x_temp",
]

RSB_TARGET_BY_STAGE_BUCKET = {
    "Vegetative": "RSB_Dead_Hearts_Pct",
    "Reproductive": "RSB_White_Ears_Pct",
}

# RSB has two differently-scaled damage indicators (dead hearts = vegetative
# stage, white ears = reproductive stage). Which one a given sample's target
# actually is must be an explicit input, not something the model has to
# infer — and it must be knowable at inference time, so it's tied to the
# WINDOW's current growth-stage bucket (known today), not the target date's
# bucket 14 days in the future (unknowable at inference time). This assumes
# the growth-stage bucket doesn't flip within the forecast horizon, which is
# reasonable given growth stages typically span well over 2 weeks.


def load_clean_daily() -> pd.DataFrame:
    df = pd.read_csv(CLEAN_DAILY_CSV, parse_dates=["Date"])
    df["growth_stage_bucket"] = df["Rice_Growth_Stage"].map(GROWTH_STAGE_BUCKETS)
    return df.sort_values(["Municipality", "Date"]).reset_index(drop=True)


def build_daily_sequence_row(day: pd.Series) -> list[float]:
    t_max, t_min, rh = [day["Tmax"]], [day["Tmin"]], [day["Relative_Humidity"]]
    vpd_daily = calculate_vpd(t_max, t_min, rh)
    diurnal_range_daily = calculate_diurnal_range(t_max, t_min)
    stage_one_hot = [1.0 if day["Rice_Growth_Stage"] == stage else 0.0 for stage in GROWTH_STAGES]
    return [
        day["Tmax"],
        day["Tmin"],
        day["Relative_Humidity"],
        day["Rainfall"],
        vpd_daily,
        diurnal_range_daily,
        *stage_one_hot,
    ]


def is_reproductive_window(window: pd.DataFrame) -> float:
    """1.0/0.0 flag from the window's LAST (most recent/current) day — the
    single source of truth for both the static feature and the RSB target
    column choice, so training and inference always agree on which bucket
    a sample belongs to."""
    return 1.0 if window["growth_stage_bucket"].iloc[-1] == "Reproductive" else 0.0


def build_static_features(window: pd.DataFrame, pest: str, is_reproductive: float) -> list[float]:
    params = PEST_PARAMS[pest]
    t_max = window["Tmax"].tolist()
    t_min = window["Tmin"].tolist()
    rh = window["Relative_Humidity"].tolist()
    rainfall = window["Rainfall"].tolist()

    gdd_accum = calculate_gdd(t_max, t_min, base_temp_c=params.gdd_base_temp_c)
    crf = calculate_crf(rainfall)
    hp = calculate_hp(rh, rh_threshold=params.hp_rh_threshold_pct)
    wsi = calculate_wsi(rainfall)
    rainfall_trend = calculate_trend(rainfall)
    temp_mean_series = [(hi + lo) / 2 for hi, lo in zip(t_max, t_min)]
    temp_trend = calculate_trend(temp_mean_series)

    reproductive_x_rainfall = is_reproductive * crf
    reproductive_x_temp = is_reproductive * (sum(temp_mean_series) / len(temp_mean_series))

    return [
        gdd_accum,
        crf,
        hp,
        wsi,
        rainfall_trend,
        temp_trend,
        is_reproductive,
        reproductive_x_rainfall,
        reproductive_x_temp,
    ]


def target_value(target_row: pd.Series, pest: str, is_reproductive: float) -> float:
    if pest == "BPH":
        return float(target_row["BPH_Hoppers_per_Hill"])
    bucket = "Reproductive" if is_reproductive else "Vegetative"
    return float(target_row[RSB_TARGET_BY_STAGE_BUCKET[bucket]])


def build_sequences_for_pest(df: pd.DataFrame, pest: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    window_days = PEST_PARAMS[pest].crf_window_days

    X_seq_rows: list[list[list[float]]] = []
    X_static_rows: list[list[float]] = []
    y_rows: list[float] = []
    meta_rows: list[dict] = []

    for municipality, group in df.groupby("Municipality"):
        group = group.reset_index(drop=True)
        n = len(group)
        last_start = n - window_days - FORECAST_HORIZON_DAYS
        for start in range(0, last_start + 1):
            window = group.iloc[start : start + window_days]
            target_idx = start + window_days + FORECAST_HORIZON_DAYS - 1
            target_row = group.iloc[target_idx]
            is_reproductive = is_reproductive_window(window)

            X_seq_rows.append([build_daily_sequence_row(window.iloc[i]) for i in range(window_days)])
            X_static_rows.append(build_static_features(window, pest, is_reproductive))
            y_rows.append(target_value(target_row, pest, is_reproductive))
            meta_rows.append(
                {
                    "municipality": municipality,
                    "window_start_date": window["Date"].iloc[0],
                    "window_end_date": window["Date"].iloc[-1],
                    "target_date": target_row["Date"],
                }
            )

    X_sequence = np.array(X_seq_rows, dtype=np.float32)
    X_static = np.array(X_static_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)
    meta = pd.DataFrame(meta_rows)
    return X_sequence, X_static, y, meta


def main() -> None:
    df = load_clean_daily()
    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}
    for pest in PEST_PARAMS:
        X_sequence, X_static, y, meta = build_sequences_for_pest(df, pest)

        npz_path = SEQUENCES_DIR / f"{pest.lower()}_sequences.npz"
        np.savez(
            npz_path,
            X_sequence=X_sequence,
            X_static=X_static,
            y=y,
            sequence_feature_columns=np.array(SEQUENCE_FEATURE_COLUMNS),
            static_feature_columns=np.array(STATIC_FEATURE_COLUMNS),
        )

        meta_path = SEQUENCES_DIR / f"{pest.lower()}_sequences_meta.csv"
        meta.to_csv(meta_path, index=False)

        summary[pest] = {
            "num_sequences": int(len(y)),
            "window_days": PEST_PARAMS[pest].crf_window_days,
            "horizon_days": FORECAST_HORIZON_DAYS,
            "X_sequence_shape": list(X_sequence.shape),
            "X_static_shape": list(X_static.shape),
            "target_mean": float(y.mean()) if len(y) else None,
            "target_std": float(y.std()) if len(y) else None,
        }
        print(f"{pest}: {len(y)} sequences -> {npz_path}")

    (SEQUENCES_DIR / "build_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

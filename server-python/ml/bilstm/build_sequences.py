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

Two feature configurations are supported, because the thesis's RQ2/RQ3
compare them head to head (see ml/bilstm/compare_features.py):

  - `engineered` (default) — everything described above. This is what the
    deployed model uses.
  - `raw` — the paper's control: "daily maximum/minimum temperature,
    relative humidity, and rainfall only". The per-day sequence keeps just
    those four columns (no VPD, no diurnal range, no growth-stage one-hot)
    and there is NO static vector at all, since every static feature is by
    definition an engineered one. ml/bilstm/train.py's build_model drops the
    static branch when the static vector is empty, so the recurrent core
    being compared stays identical.

Run from server-python/:
    .venv/Scripts/python.exe -m ml.bilstm.build_sequences
    .venv/Scripts/python.exe -m ml.bilstm.build_sequences --features raw

Output: one .npz per pest in ml/datasets/processed/sequences/, holding
X_sequence (num_samples, window_days, num_seq_features), X_static
(num_samples, num_static_features), y (num_samples,), and both feature
column orders — plus a matching metadata CSV (municipality, window
start/end date, target date, is_reproductive) so a prediction can be traced
back to its source rows and bucketed for the ETL check. The `raw`
configuration writes to `{pest}_sequences_raw.npz` so it never overwrites
the deployed model's inputs.
"""

import argparse
import json
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from ml.ablation import hand_features_vectorized as vf
from ml.ablation.hand_features import (
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
    PROCESSED_DATA_DIR,
    SEQUENCES_DIR,
)

# Produced by ml/bilstm/ingest_reports.py (run that first, as part of the
# periodic retrain, to pick up verified farmer reports since the last run).
# Optional: if it doesn't exist yet, training proceeds on the historical
# CSV alone, same as before this file existed.
REPORTS_DAILY_CSV = PROCESSED_DATA_DIR / "weather_pest_daily_from_reports.csv"

GROWTH_STAGES = ["Seedling", "Tillering", "Elongation", "Panicle", "Flowering", "Ripening"]

# The paper's "raw, unengineered climate variables" control set.
RAW_SEQUENCE_FEATURE_COLUMNS = [
    "Tmax",
    "Tmin",
    "Relative_Humidity",
    "Rainfall",
]

SEQUENCE_FEATURE_COLUMNS = [
    *RAW_SEQUENCE_FEATURE_COLUMNS,
    "vpd_daily",
    "diurnal_range_daily",
    *[f"growth_stage_{stage.lower()}" for stage in GROWTH_STAGES],
]

# A third control, alongside `raw`: can the BiLSTM learn the hand-computed
# aggregates (GDD, CRF, HP, WSI, trends) itself from exposure to the raw
# daily series, if given the SAME information the engineered model gets
# minus only the engineered math? Unlike `raw`, this keeps growth stage in
# the sequence (dropping it would confound "can the recurrent core learn
# the climate aggregation" with "does it also lose phenology", and SHAP
# attributes ~45% of the engineered model's output to growth stage alone,
# so losing it would swamp any climate-feature effect). It also drops VPD
# and diurnal range, since both are themselves engineered quantities, not
# raw observations. There is still no static branch: every candidate for
# the static vector (GDD/CRF/HP/WSI/trends) is exactly what this
# configuration is testing whether the LSTM can reconstruct on its own.
SEQ_ONLY_FEATURE_COLUMNS = [
    *RAW_SEQUENCE_FEATURE_COLUMNS,
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

LAGGED_FEATURE_COLUMNS = [
    "last_observed_value",
    "days_since_observation",
    "has_recent_observation",
]

# How the `lagged` configuration simulates field reporting. The historical CSV
# has a pest value on EVERY day, but the deployed system only ever sees a value
# when a farmer submits a report and a technologist verifies it — which is
# sparse and irregular (see ml/bilstm/ingest_reports.py: one row per reported
# day, not one per calendar day). Training on "yesterday's value, always
# available" would therefore teach the model something inference can never
# supply, and the model would lean on a feature that is usually stale or
# missing in production.
#
# So observation days are thinned to a simulated reporting cadence before the
# lag features are computed: gaps are drawn from a geometric distribution with
# this mean, per municipality, from a fixed seed so every rebuild is identical.
OBSERVATION_GAP_MEAN_DAYS = 14
# Past this age an observation is treated as unusable: the value is zeroed and
# has_recent_observation flips to 0, so the model learns to fall back on
# climate alone rather than trusting a months-old count.
MAX_OBSERVATION_AGE_DAYS = 60
OBSERVATION_SEED = 20260101

# `lagged_fresh`: instead of the cadence above (which leaves ~98% of windows
# with a report, typically ~9 days old), each window independently gets no
# report with probability FRESH_NO_REPORT_PROB, otherwise one whose age is
# uniform over 0..FRESH_MAX_AGE_DAYS. Live, most municipalities have no
# recent report and the ones that do can be any age, so the model needs to
# see both cases, and fresh reports often enough to learn how much a recent
# count should move a 14-day-ahead forecast. Ages past FRESH_MAX_AGE_DAYS
# carry almost no information about the target in this dataset (lag-28
# autocorrelation beyond growth stage is ~0.2 for BPH), so they're folded
# into "no report".
FRESH_NO_REPORT_PROB = 0.5
FRESH_MAX_AGE_DAYS = 30

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
    """The historical dataset, plus any verified-report-derived rows from
    ml/bilstm/ingest_reports.py when that script has been run — this is the
    "continuous learning" seam: a report never touches a live forecast (see
    app/routers/inference.py's _run_forecast docstring), but it does show up
    here as training data for the next periodic retrain.

    A report-derived row's municipality+date can duplicate a row already in
    CLEAN_DAILY_CSV (e.g. a report for a date the historical set already
    covers) — the report-derived row wins, since a verified farmer report is
    more direct ground truth for that pest than the historical dataset's own
    value. Only one pest's columns are ever set on a report-derived row; the
    other pest's columns are left as whatever the historical row already had
    (or NaN if there wasn't one), not overwritten with NaN.
    """
    df = pd.read_csv(CLEAN_DAILY_CSV, parse_dates=["Date"])

    if REPORTS_DAILY_CSV.exists():
        reports_df = pd.read_csv(REPORTS_DAILY_CSV, parse_dates=["Date"])
        if not reports_df.empty:
            pest_columns = ["BPH_Hoppers_per_Hill", "RSB_Dead_Hearts_Pct", "RSB_White_Ears_Pct"]
            df = df.set_index(["Municipality", "Date"])
            reports_df = reports_df.set_index(["Municipality", "Date"])
            for col in pest_columns:
                df[col] = reports_df[col].combine_first(df[col]) if col in reports_df else df[col]
            # New (municipality, date) pairs the historical set never had at all.
            new_keys = reports_df.index.difference(df.index)
            if len(new_keys):
                df = pd.concat([df, reports_df.loc[new_keys]])
            df = df.reset_index()

    df["growth_stage_bucket"] = df["Rice_Growth_Stage"].map(GROWTH_STAGE_BUCKETS)
    return df.sort_values(["Municipality", "Date"]).reset_index(drop=True)


def build_daily_sequence_row(day: pd.Series, feature_set: str = "engineered") -> list[float]:
    raw = [day["Tmax"], day["Tmin"], day["Relative_Humidity"], day["Rainfall"]]
    if feature_set == "raw":
        return raw

    stage_one_hot = [1.0 if day["Rice_Growth_Stage"] == stage else 0.0 for stage in GROWTH_STAGES]
    if feature_set in ("seq_only", "plain_fresh"):
        return [*raw, *stage_one_hot]

    t_max, t_min, rh = [day["Tmax"]], [day["Tmin"]], [day["Relative_Humidity"]]
    vpd_daily = calculate_vpd(t_max, t_min, rh)
    diurnal_range_daily = calculate_diurnal_range(t_max, t_min)
    return [*raw, vpd_daily, diurnal_range_daily, *stage_one_hot]


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


def _stable_seed(municipality: str) -> int:
    """Per-municipality seed that is the same in every Python process. The
    built-in hash() of a str is randomised per process (PYTHONHASHSEED), so
    seeding from it made "every rebuild is identical" untrue: the simulated
    reporting days changed on each run. crc32 is fixed."""
    return zlib.crc32(municipality.encode("utf-8"))


def simulated_observation_days(municipality: str, n_days: int) -> np.ndarray:
    """Boolean mask over a municipality's rows: True where a verified report is
    pretended to exist. Seeded per municipality so the mask is stable across
    rebuilds — an unstable mask would silently change the training set every
    time sequences were regenerated."""
    rng = np.random.default_rng(_stable_seed(municipality) ^ OBSERVATION_SEED)
    mask = np.zeros(n_days, dtype=bool)
    day = int(rng.geometric(1 / OBSERVATION_GAP_MEAN_DAYS))
    while day < n_days:
        mask[day] = True
        day += int(rng.geometric(1 / OBSERVATION_GAP_MEAN_DAYS))
    return mask


def build_lagged_features(
    group: pd.DataFrame, observed: np.ndarray, window_end_idx: int, pest: str, is_reproductive: float
) -> list[float]:
    """The most recent SIMULATED-observed pest value at or before the window's
    last day, and how old it is.

    Strictly at-or-before `window_end_idx`, never after: the target sits
    FORECAST_HORIZON_DAYS later, so reading any row past the window end would
    leak it. Units match the target (hoppers/hill for BPH; the stage-matched
    RSB indicator), so the feature and the label are on the same scale.
    """
    for idx in range(window_end_idx, -1, -1):
        if not observed[idx]:
            continue
        age = window_end_idx - idx
        if age > MAX_OBSERVATION_AGE_DAYS:
            break
        value = target_value(group.iloc[idx], pest, is_reproductive)
        if pd.isna(value):
            continue
        return [float(value), float(age), 1.0]

    # Nothing recent enough — the honest encoding of "no report on file".
    return [0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0]


def build_fresh_lagged_features(
    group: pd.DataFrame, rng: np.random.Generator, window_end_idx: int, pest: str, is_reproductive: float
) -> list[float]:
    """`lagged_fresh` counterpart to build_lagged_features: either the "no
    report on file" encoding, or the stage-matched pest value from a day
    0..FRESH_MAX_AGE_DAYS before the window ends (never after, so the target
    can't leak), with its age."""
    if rng.random() < FRESH_NO_REPORT_PROB:
        return [0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0]
    age = int(rng.integers(0, FRESH_MAX_AGE_DAYS + 1))
    idx = window_end_idx - age
    if idx < 0:
        return [0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0]
    value = target_value(group.iloc[idx], pest, is_reproductive)
    if pd.isna(value):
        return [0.0, float(MAX_OBSERVATION_AGE_DAYS), 0.0]
    return [float(value), float(age), 1.0]


def target_value(target_row: pd.Series, pest: str, is_reproductive: float) -> float:
    if pest == "BPH":
        return float(target_row["BPH_Hoppers_per_Hill"])
    bucket = "Reproductive" if is_reproductive else "Vegetative"
    return float(target_row[RSB_TARGET_BY_STAGE_BUCKET[bucket]])


def build_sequences_for_pest(
    df: pd.DataFrame, pest: str, feature_set: str = "engineered", lagged: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    window_days = PEST_PARAMS[pest].crf_window_days

    X_seq_rows: list[list[list[float]]] = []
    X_static_rows: list[list[float]] = []
    y_rows: list[float] = []
    meta_rows: list[dict] = []

    for municipality, group in df.groupby("Municipality"):
        group = group.reset_index(drop=True)
        n = len(group)
        observed = simulated_observation_days(municipality, n) if lagged else None
        rng = np.random.default_rng(_stable_seed(municipality) ^ OBSERVATION_SEED)
        last_start = n - window_days - FORECAST_HORIZON_DAYS
        for start in range(0, last_start + 1):
            window = group.iloc[start : start + window_days]
            target_idx = start + window_days + FORECAST_HORIZON_DAYS - 1
            target_row = group.iloc[target_idx]
            is_reproductive = is_reproductive_window(window)

            X_seq_rows.append(
                [build_daily_sequence_row(window.iloc[i], feature_set) for i in range(window_days)]
            )
            # raw/seq_only: no static vector at all (every static feature is
            # an engineered one), but the row is still appended as an empty
            # list so X_static keeps shape (num_samples, 0) rather than (0,).
            static_row = (
                build_static_features(window, pest, is_reproductive)
                if feature_set in ("engineered", "lagged", "lagged_fresh")
                else []
            )
            if feature_set in ("lagged_fresh", "plain_fresh"):
                static_row = static_row + build_fresh_lagged_features(
                    group, rng, start + window_days - 1, pest, is_reproductive
                )
            elif lagged:
                static_row = static_row + build_lagged_features(
                    group, observed, start + window_days - 1, pest, is_reproductive
                )
            X_static_rows.append(static_row)
            y_rows.append(target_value(target_row, pest, is_reproductive))
            meta_rows.append(
                {
                    "municipality": municipality,
                    "window_start_date": window["Date"].iloc[0],
                    "window_end_date": window["Date"].iloc[-1],
                    "target_date": target_row["Date"],
                    # Not a feature — carried so ml/bilstm/etl_metrics.py can
                    # pick the right ETL band per sample in BOTH configurations.
                    "is_reproductive": int(is_reproductive),
                }
            )

    X_sequence = np.array(X_seq_rows, dtype=np.float32)
    X_static = np.array(X_static_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)
    meta = pd.DataFrame(meta_rows)
    return X_sequence, X_static, y, meta


def build_sequences_for_pest_vectorized(
    df: pd.DataFrame, pest: str, feature_set: str = "engineered", lagged: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    """Same output as build_sequences_for_pest, computed per municipality in
    one vectorized pass instead of a Python loop over every window and day
    (ml/ablation/hand_features_vectorized.py). Each daily term is computed
    once and window aggregates come from sliding-window views, so the 13 of
    14 days consecutive windows share are no longer recomputed.

    Only the report-observation columns of the lagged configurations are
    still drawn window by window, because they consume a seeded random
    stream in window order and must match the loop version draw for draw.
    """
    params = PEST_PARAMS[pest]
    window_days = params.crf_window_days

    seq_parts, static_parts, y_parts, meta_parts = [], [], [], []
    for municipality, group in df.groupby("Municipality"):
        group = group.reset_index(drop=True)
        n = len(group)
        n_windows = n - window_days - FORECAST_HORIZON_DAYS + 1
        if n_windows <= 0:
            continue

        tmax = group["Tmax"].to_numpy(dtype=np.float64)
        tmin = group["Tmin"].to_numpy(dtype=np.float64)
        rh = group["Relative_Humidity"].to_numpy(dtype=np.float64)
        rain = group["Rainfall"].to_numpy(dtype=np.float64)
        stage = group["Rice_Growth_Stage"].to_numpy()
        stage_one_hot = np.stack([(stage == s).astype(np.float64) for s in GROWTH_STAGES], axis=1)

        columns = [tmax, tmin, rh, rain]
        if feature_set in ("seq_only", "plain_fresh"):
            daily = np.column_stack(columns + [stage_one_hot])
        elif feature_set == "raw":
            daily = np.column_stack(columns)
        else:
            daily = np.column_stack(
                columns + [vf.daily_vpd(tmax, tmin, rh), vf.daily_diurnal_range(tmax, tmin), stage_one_hot]
            )
        # (n - window + 1, n_features, window) -> (windows, window, features)
        windows = np.lib.stride_tricks.sliding_window_view(daily, window_days, axis=0).transpose(0, 2, 1)
        seq_parts.append(windows[:n_windows])

        ends = np.arange(n_windows) + window_days - 1
        is_reproductive = (group["growth_stage_bucket"].to_numpy()[ends] == "Reproductive").astype(np.float64)

        if feature_set in ("engineered", "lagged", "lagged_fresh"):
            static = vf.static_features(
                tmax, tmin, rh, rain, np.zeros(n - window_days + 1), window_days, params.gdd_base_temp_c, params.hp_rh_threshold_pct
            )[:n_windows]
            static[:, 6] = is_reproductive
            static[:, 7] = is_reproductive * static[:, 1]
            temp_mean_window = vf.window_mean((tmax + tmin) / 2, window_days)[:n_windows]
            static[:, 8] = is_reproductive * temp_mean_window
        else:
            static = np.zeros((n_windows, 0))

        if lagged:
            observed = simulated_observation_days(municipality, n) if feature_set == "lagged" else None
            rng = np.random.default_rng(_stable_seed(municipality) ^ OBSERVATION_SEED)
            obs = np.array(
                [
                    build_fresh_lagged_features(group, rng, int(end), pest, float(rep))
                    if feature_set in ("lagged_fresh", "plain_fresh")
                    else build_lagged_features(group, observed, int(end), pest, float(rep))
                    for end, rep in zip(ends, is_reproductive)
                ]
            )
            static = np.hstack([static, obs])
        static_parts.append(static)

        targets = ends + FORECAST_HORIZON_DAYS
        if pest == "BPH":
            y = group["BPH_Hoppers_per_Hill"].to_numpy()[targets]
        else:
            y = np.where(
                is_reproductive == 1.0,
                group[RSB_TARGET_BY_STAGE_BUCKET["Reproductive"]].to_numpy()[targets],
                group[RSB_TARGET_BY_STAGE_BUCKET["Vegetative"]].to_numpy()[targets],
            )
        y_parts.append(y)

        dates = group["Date"]
        meta_parts.append(
            pd.DataFrame(
                {
                    "municipality": municipality,
                    "window_start_date": dates.iloc[ends - window_days + 1].to_numpy(),
                    "window_end_date": dates.iloc[ends].to_numpy(),
                    "target_date": dates.iloc[targets].to_numpy(),
                    "is_reproductive": is_reproductive.astype(int),
                }
            )
        )

    return (
        np.concatenate(seq_parts).astype(np.float32),
        np.concatenate(static_parts).astype(np.float32),
        np.concatenate(y_parts).astype(np.float32),
        pd.concat(meta_parts, ignore_index=True),
    )


def verify_against_loop(df: pd.DataFrame, pest: str, feature_set: str, lagged: bool) -> None:
    """Fails loudly if the vectorized builder ever disagrees with the
    original per-window loop (build_sequences_for_pest)."""
    a = build_sequences_for_pest(df, pest, feature_set, lagged)
    b = build_sequences_for_pest_vectorized(df, pest, feature_set, lagged)
    for name, x, z in zip(("X_sequence", "X_static", "y"), a[:3], b[:3]):
        if x.shape != z.shape or not np.allclose(x, z, atol=1e-4, rtol=1e-5):
            raise SystemExit(f"vectorized {name} differs from the loop version for {pest}/{feature_set}")
    for col in ("municipality", "window_start_date", "window_end_date", "target_date", "is_reproductive"):
        if not (a[3][col].astype(str).to_numpy() == b[3][col].astype(str).to_numpy()).all():
            raise SystemExit(f"vectorized meta column {col} differs for {pest}/{feature_set}")


FEATURE_SET_SUFFIX = {
    "engineered": "",
    "raw": "_raw",
    "lagged": "_lagged",
    "lagged_fresh": "_lagged_fresh",
    "seq_only": "_seqonly",
    "plain_fresh": "_plain_fresh",
}


def sequences_path(pest: str, feature_set: str = "engineered") -> tuple[Path, Path]:
    """(npz, meta csv) for one pest + feature configuration. The engineered
    set keeps the original filenames so existing trained models and scalers
    still line up."""
    suffix = FEATURE_SET_SUFFIX[feature_set]
    return (
        SEQUENCES_DIR / f"{pest.lower()}_sequences{suffix}.npz",
        SEQUENCES_DIR / f"{pest.lower()}_sequences{suffix}_meta.csv",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        choices=["engineered", "raw", "lagged", "lagged_fresh", "seq_only", "plain_fresh"],
        default="engineered",
        help="engineered = the deployed feature set; raw = the paper's RQ2 control "
        "(Tmax/Tmin/RH/rainfall only); lagged = engineered plus the simulated "
        "last-verified-observation features; seq_only = raw climate + growth "
        "stage in the sequence, no hand-computed aggregates — tests whether "
        "the LSTM can learn GDD/CRF/HP/WSI/trends itself; plain_fresh = seq_only "
        "plus the verified-observation values (no formulas anywhere): the framework "
        "as the panel asked for it",
    )
    args = parser.parse_args()
    feature_set = args.features
    lagged = args.features in ("lagged", "lagged_fresh", "plain_fresh")

    df = load_clean_daily()
    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)

    static_columns = (STATIC_FEATURE_COLUMNS if feature_set in ("engineered", "lagged", "lagged_fresh") else []) + (
        LAGGED_FEATURE_COLUMNS if lagged else []
    )

    sequence_columns_by_set = {
        "engineered": SEQUENCE_FEATURE_COLUMNS,
        "raw": RAW_SEQUENCE_FEATURE_COLUMNS,
        "lagged": SEQUENCE_FEATURE_COLUMNS,
        "lagged_fresh": SEQUENCE_FEATURE_COLUMNS,
        "seq_only": SEQ_ONLY_FEATURE_COLUMNS,
        "plain_fresh": SEQ_ONLY_FEATURE_COLUMNS,
    }

    summary = {}
    for pest in PEST_PARAMS:
        X_sequence, X_static, y, meta = build_sequences_for_pest_vectorized(df, pest, feature_set, lagged)
        npz_path, meta_path = sequences_path(pest, args.features)

        np.savez(
            npz_path,
            X_sequence=X_sequence,
            X_static=X_static,
            y=y,
            sequence_feature_columns=np.array(sequence_columns_by_set[feature_set]),
            static_feature_columns=np.array(static_columns, dtype=object),
        )

        meta.to_csv(meta_path, index=False)

        summary[pest] = {
            "feature_set": args.features,
            "num_sequences": int(len(y)),
            "window_days": PEST_PARAMS[pest].crf_window_days,
            "horizon_days": FORECAST_HORIZON_DAYS,
            "X_sequence_shape": list(X_sequence.shape),
            "X_static_shape": list(X_static.shape),
            "target_mean": float(y.mean()) if len(y) else None,
            "target_std": float(y.std()) if len(y) else None,
        }
        print(f"{pest} ({args.features}): {len(y)} sequences -> {npz_path}")

    summary_name = f"build_summary{FEATURE_SET_SUFFIX[args.features]}.json"
    (SEQUENCES_DIR / summary_name).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Vectorized feature engineering: every window's features in one pass.

app/preprocessing/features.py defines each biologically-informed feature as a
plain function over ONE window's daily lists, and ml/bilstm/build_sequences.py
used to call those functions window by window, day by day, through pandas
row access. For one live forecast that is fine; for building a training set
(~10,800 overlapping 14-day windows per pest) it recomputes the same sums
thousands of times, since consecutive windows share 13 of their 14 days.

This module computes the same quantities for all windows of a series at once:
each daily term is computed once per day, and window aggregates come from
sliding-window views (numpy.lib.stride_tricks.sliding_window_view), so there
is no Python loop over windows or days. The formulas are exactly those in
features.py, and ml/bilstm/build_sequences.py checks the two implementations
agree before using this one (see verify_against_loop there).

All functions take 1-D daily arrays for ONE municipality's series and return
one value (or row) per window, where window k covers days k .. k+window-1.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.preprocessing.features import (
    GDD_BASE_TEMP_C,
    HUMIDITY_PERSISTENCE_THRESHOLD,
    WSI_DAILY_WATER_REQUIREMENT_MM,
)


def _windows(x: np.ndarray, window: int) -> np.ndarray:
    """(n_windows, window) view, no copy."""
    return sliding_window_view(np.asarray(x, dtype=np.float64), window)


def daily_vpd(tmax: np.ndarray, tmin: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Per-day vapor pressure deficit (kPa), FAO-56, from the daily mean temp.
    Same formula as features.calculate_vpd applied to a single day."""
    t_mean = (np.asarray(tmax) + np.asarray(tmin)) / 2
    saturation = 0.6108 * np.exp(17.27 * t_mean / (t_mean + 237.3))
    return saturation - saturation * (np.asarray(rh) / 100)


def daily_diurnal_range(tmax: np.ndarray, tmin: np.ndarray) -> np.ndarray:
    return np.asarray(tmax) - np.asarray(tmin)


def window_gdd(tmax, tmin, window: int, base_temp_c: float = GDD_BASE_TEMP_C) -> np.ndarray:
    daily = np.maximum((np.asarray(tmax) + np.asarray(tmin)) / 2 - base_temp_c, 0.0)
    return _windows(daily, window).sum(axis=1)


def window_crf(rainfall, window: int) -> np.ndarray:
    return _windows(rainfall, window).sum(axis=1)


def window_hp(rh, window: int, rh_threshold: float = HUMIDITY_PERSISTENCE_THRESHOLD) -> np.ndarray:
    return (_windows(rh, window) >= rh_threshold).mean(axis=1) * 100


def window_wsi(rainfall, window: int, daily_requirement_mm: float = WSI_DAILY_WATER_REQUIREMENT_MM) -> np.ndarray:
    requirement = daily_requirement_mm * window
    deficit = np.maximum(requirement - window_crf(rainfall, window), 0.0)
    return np.minimum(deficit / requirement, 1.0)


def window_trend(series, window: int) -> np.ndarray:
    """Least-squares slope per window. With x centred on its mean, the slope
    is sum(x_c * y) / sum(x_c^2), a fixed dot product applied to every
    window at once."""
    x_c = np.arange(window) - (window - 1) / 2
    return _windows(series, window) @ x_c / np.sum(x_c**2)


def window_mean(series, window: int) -> np.ndarray:
    return _windows(series, window).mean(axis=1)


def static_features(
    tmax, tmin, rh, rainfall, is_reproductive: np.ndarray, window: int, gdd_base_temp_c: float, hp_rh_threshold_pct: float
) -> np.ndarray:
    """(n_windows, 9) static vector in build_sequences.STATIC_FEATURE_COLUMNS
    order. `is_reproductive` is per window (from its last day)."""
    temp_mean = (np.asarray(tmax) + np.asarray(tmin)) / 2
    crf = window_crf(rainfall, window)
    is_reproductive = np.asarray(is_reproductive, dtype=np.float64)
    return np.column_stack(
        [
            window_gdd(tmax, tmin, window, gdd_base_temp_c),
            crf,
            window_hp(rh, window, hp_rh_threshold_pct),
            window_wsi(rainfall, window),
            window_trend(rainfall, window),
            window_trend(temp_mean, window),
            is_reproductive,
            is_reproductive * crf,
            is_reproductive * window_mean(temp_mean, window),
        ]
    )

"""Engineered biological features used by the BiLSTM outbreak forecaster.

These are the Python/canonical versions of the same metrics already computed
client-side in admin-web (see src/pages/Dashboard/Dashboard.tsx,
`deriveClimateMetrics`) for the dashboard's "Crop Context & Climate Drivers"
card. Centralizing them here means the ML pipeline and the dashboard agree on
definitions — if you change a formula, update it in both places (or, longer
term, have admin-web call a /api/features endpoint that uses this module
instead of duplicating the math in TypeScript).
"""

import math

# Defaults only — GDD base temp and HP threshold differ per pest (BPH vs RSB).
# Callers building per-pest features should pass ml/config.py's PEST_PARAMS
# values explicitly rather than relying on these.
GDD_BASE_TEMP_C = 10.0
HUMIDITY_PERSISTENCE_THRESHOLD = 80.0

# Typical lowland rice daily water requirement (mm/day), used as the WSI
# reference demand in the absence of measured evapotranspiration. Confirm
# against a cited source before treating as final.
WSI_DAILY_WATER_REQUIREMENT_MM = 6.0


def calculate_gdd(
    daily_temp_max: list[float],
    daily_temp_min: list[float],
    base_temp_c: float = GDD_BASE_TEMP_C,
) -> float:
    """Growing Degree Days, summed over the given daily max/min temperature series."""
    total = 0.0
    for t_max, t_min in zip(daily_temp_max, daily_temp_min):
        mean_temp = (t_max + t_min) / 2
        total += max(mean_temp - base_temp_c, 0.0)
    return total


def calculate_crf(daily_precipitation_mm: list[float]) -> float:
    """Cumulative Rainfall Factor: total rainfall (mm) over the given period."""
    return sum(daily_precipitation_mm)


def calculate_hp(
    daily_relative_humidity: list[float],
    rh_threshold: float = HUMIDITY_PERSISTENCE_THRESHOLD,
) -> float:
    """Humidity Persistence: % of days at/above the high-humidity threshold
    that favors pest development (e.g. Brown Planthopper)."""
    if not daily_relative_humidity:
        return 0.0
    above_threshold = sum(1 for rh in daily_relative_humidity if rh >= rh_threshold)
    return (above_threshold / len(daily_relative_humidity)) * 100


def calculate_vpd(
    daily_temp_max: list[float],
    daily_temp_min: list[float],
    daily_relative_humidity: list[float],
) -> float:
    """Mean Vapor Pressure Deficit (kPa) over the given period, via the FAO-56
    saturation vapor pressure formula applied to daily mean temperature."""
    n = len(daily_temp_max)
    if n == 0:
        return 0.0
    total = 0.0
    for t_max, t_min, rh in zip(daily_temp_max, daily_temp_min, daily_relative_humidity):
        t_mean = (t_max + t_min) / 2
        saturation_vp = 0.6108 * math.exp(17.27 * t_mean / (t_mean + 237.3))
        actual_vp = saturation_vp * (rh / 100)
        total += saturation_vp - actual_vp
    return total / n


def calculate_wsi(
    daily_precipitation_mm: list[float],
    daily_water_requirement_mm: float = WSI_DAILY_WATER_REQUIREMENT_MM,
) -> float:
    """Water Stress Index: fraction of crop water requirement over the period
    NOT met by rainfall, clipped to [0, 1]. 0 = rainfall met/exceeded demand,
    1 = no rainfall at all. Simplified rainfall-deficit proxy used in place of
    measured evapotranspiration — confirm/cite before treating as final."""
    n = len(daily_precipitation_mm)
    if n == 0:
        return 0.0
    requirement = daily_water_requirement_mm * n
    if requirement <= 0:
        return 0.0
    supplied = sum(daily_precipitation_mm)
    deficit = max(requirement - supplied, 0.0)
    return min(deficit / requirement, 1.0)


def calculate_diurnal_range(daily_temp_max: list[float], daily_temp_min: list[float]) -> float:
    """Mean diurnal temperature range (Tmax - Tmin) over the given period."""
    if not daily_temp_max:
        return 0.0
    return sum(t_max - t_min for t_max, t_min in zip(daily_temp_max, daily_temp_min)) / len(daily_temp_max)


def calculate_trend(daily_series: list[float]) -> float:
    """Linear trend (rate of change per day) over the given period, via a
    simple least-squares slope. Positive = rising, negative = falling."""
    n = len(daily_series)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(daily_series) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_series))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0

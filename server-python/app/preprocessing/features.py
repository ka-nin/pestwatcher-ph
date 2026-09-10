"""Engineered biological features used by the BiLSTM outbreak forecaster.

These are the Python/canonical versions of the same metrics already computed
client-side in admin-web (see src/pages/Dashboard/Dashboard.tsx,
`deriveClimateMetrics`) for the dashboard's "Crop Context & Climate Drivers"
card. Centralizing them here means the ML pipeline and the dashboard agree on
definitions — if you change a formula, update it in both places (or, longer
term, have admin-web call a /api/features endpoint that uses this module
instead of duplicating the math in TypeScript).
"""

GDD_BASE_TEMP_C = 10.0
HUMIDITY_PERSISTENCE_THRESHOLD = 80.0


def calculate_gdd(daily_temp_max: list[float], daily_temp_min: list[float]) -> float:
    """Growing Degree Days, summed over the given daily max/min temperature series."""
    total = 0.0
    for t_max, t_min in zip(daily_temp_max, daily_temp_min):
        mean_temp = (t_max + t_min) / 2
        total += max(mean_temp - GDD_BASE_TEMP_C, 0.0)
    return total


def calculate_crf(daily_precipitation_mm: list[float]) -> float:
    """Cumulative Rainfall Factor: total rainfall (mm) over the given period."""
    return sum(daily_precipitation_mm)


def calculate_hp(hourly_relative_humidity: list[float]) -> float:
    """Humidity Persistence: % of hours at/above the high-humidity threshold
    that favors pest development (e.g. Brown Planthopper)."""
    if not hourly_relative_humidity:
        return 0.0
    above_threshold = sum(1 for rh in hourly_relative_humidity if rh >= HUMIDITY_PERSISTENCE_THRESHOLD)
    return (above_threshold / len(hourly_relative_humidity)) * 100

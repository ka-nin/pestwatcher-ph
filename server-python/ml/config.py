"""Per-pest biological parameters and shared training paths.

This is the single source of truth for the "finalized parameters" table in
the thesis. ml/bilstm/build_sequences.py (training) and
app/preprocessing/features.py (inference) should both read from here rather
than hardcoding T_base/window/threshold values in two places.

Values marked with a comment are literature defaults picked to unblock the
pipeline — confirm/cite them against your actual sources before treating
them as final, especially CRF_WINDOW_DAYS (your RSB literature review
mentions both 14- and 28-day windows; 14 was picked here to match the
already-collected weather series, not because 28 was ruled out).
"""

from dataclasses import dataclass
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
WEIGHTS_DIR = ML_DIR / "weights"
PROCESSED_DATA_DIR = ML_DIR / "datasets" / "processed"

CLEAN_DAILY_CSV = PROCESSED_DATA_DIR / "weather_pest_daily_clean.csv"
SEQUENCES_DIR = PROCESSED_DATA_DIR / "sequences"

# BiLSTM forecasts this many days ahead (thesis scope: 2-week horizon).
FORECAST_HORIZON_DAYS = 14


@dataclass(frozen=True)
class PestParams:
    gdd_base_temp_c: float  # T_base for Growing Degree Days
    crf_window_days: int  # rolling window for Cumulative Rainfall Factor
    hp_window_days: int  # rolling window for Humidity Persistence
    hp_rh_threshold_pct: float  # RH% considered "high humidity" for HP
    resnet_weights_path: Path
    bilstm_weights_path: Path


PEST_PARAMS: dict[str, PestParams] = {
    "BPH": PestParams(
        gdd_base_temp_c=10.0,  # brown planthopper dev. threshold; BPH microclimate lit. ~9-10C
        crf_window_days=14,
        hp_window_days=14,
        hp_rh_threshold_pct=80.0,  # BPH microclimate literature
        resnet_weights_path=WEIGHTS_DIR / "bph" / "resnet50_bph.keras",
        bilstm_weights_path=WEIGHTS_DIR / "bph" / "bilstm_bph.keras",
    ),
    "RSB": PestParams(
        gdd_base_temp_c=15.0,  # per thesis RSB literature review
        crf_window_days=14,  # confirm vs. 28-day alternative cited in RSB literature review
        hp_window_days=14,
        hp_rh_threshold_pct=80.0,
        resnet_weights_path=WEIGHTS_DIR / "rsb" / "resnet50_rsb.keras",
        bilstm_weights_path=WEIGHTS_DIR / "rsb" / "bilstm_rsb.keras",
    ),
}

# Table 1's six growth stages collapse into the two buckets the ETL check
# (Table 2) and app/decision/etl_thresholds.py operate on.
GROWTH_STAGE_BUCKETS: dict[str, str] = {
    "Seedling": "Vegetative",
    "Tillering": "Vegetative",
    "Elongation": "Vegetative",
    "Panicle": "Reproductive",
    "Flowering": "Reproductive",
    "Ripening": "Reproductive",
}

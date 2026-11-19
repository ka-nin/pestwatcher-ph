"""Fixed, non-learned interpretation of the BiLSTM's continuous forecast
into a Low/Medium/High IPM decision level, per the thesis's Table 2
("Economic Threshold Level (ETL) Numerical Values by Pest Species, Crop
Stage, and Risk Classification" — Thesis Writing_Group 4.pdf, p.57-58).

This is deliberately separate from app/models/bilstm_model.py — per the
panel's fix #1, the model forecasts a continuous value (hoppers/hill,
% damage) and ETL only buckets it against a fixed agronomic standard. The
model must never learn its own definition of "high risk"; if a threshold
needs to change, it changes here, not by retraining.

These values are transcribed directly from Table 2 and are stage-specific:
BPH thresholds are stricter during Reproductive than Vegetative, and RSB
uses a different damage indicator per stage (% dead hearts vegetative,
% white ears reproductive — matches RSB_TARGET_BY_STAGE_BUCKET in
ml/bilstm/build_sequences.py, so the target the model was trained to
predict for a given stage is the same one interpreted here).
"""

from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["Low", "Medium", "High"]
GrowthStageBucket = Literal["Vegetative", "Reproductive"]


@dataclass(frozen=True)
class ThresholdBand:
    low_max: float  # predicted_value < low_max -> Low
    high_min: float  # predicted_value >= high_min -> High
    # low_max <= predicted_value < high_min -> Medium


# Table 2, transcribed exactly:
#   BPH Vegetative:   Low <10, Medium 10-20, High >20 hoppers/hill
#   BPH Reproductive: Low <5,  Medium 5-10,  High >10 hoppers/hill
#   RSB Vegetative:   Low <2%, Medium 2-5%,  High >5%  dead hearts
#   RSB Reproductive: Low <5%, Medium 5-10%, High >10% white ears
PEST_THRESHOLDS: dict[str, dict[GrowthStageBucket, ThresholdBand]] = {
    "BPH": {
        "Vegetative": ThresholdBand(low_max=10.0, high_min=20.0),
        "Reproductive": ThresholdBand(low_max=5.0, high_min=10.0),
    },
    "RSB": {
        "Vegetative": ThresholdBand(low_max=2.0, high_min=5.0),
        "Reproductive": ThresholdBand(low_max=5.0, high_min=10.0),
    },
}


def derive_risk_level(pest: str, growth_stage_bucket: GrowthStageBucket, predicted_value: float) -> RiskLevel:
    band = PEST_THRESHOLDS[pest][growth_stage_bucket]
    if predicted_value < band.low_max:
        return "Low"
    if predicted_value >= band.high_min:
        return "High"
    return "Medium"


def high_possible(pest: str, growth_stage_bucket: GrowthStageBucket, upper_bound: float | None) -> bool | None:
    """Early warning, kept SEPARATE from the risk level: True when the top of the forecast's 80%
    band reaches the High threshold, i.e. High is plausible even though the central forecast is
    below it. It asks for scouting, not spraying; the risk level stays the Table 2 reading of the
    central forecast. None when there is no band (the ensemble runs are not installed).

    Why: the central forecast is pulled toward the common Low windows, so on its own it caught only
    10 of 132 High BPH test windows. With this warning 60 of 132 are caught (61% on validation),
    at the cost of flagging 6.6% of truly Low windows (ml/weights/bph/bilstm_bph_early_warning.json).
    The band was calibrated before this rule existed, so nothing was tuned to produce these numbers."""
    if upper_bound is None:
        return None
    return upper_bound >= PEST_THRESHOLDS[pest][growth_stage_bucket].high_min

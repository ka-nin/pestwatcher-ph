"""The risk level follows Table 2 exactly; the early warning never changes it."""

from app.decision.etl_thresholds import derive_risk_level, high_possible


def test_risk_level_follows_table_2():
    assert derive_risk_level("BPH", "Vegetative", 9.9) == "Low"
    assert derive_risk_level("BPH", "Vegetative", 10.0) == "Medium"
    assert derive_risk_level("BPH", "Vegetative", 20.0) == "High"
    assert derive_risk_level("BPH", "Reproductive", 10.0) == "High"
    assert derive_risk_level("RSB", "Reproductive", 9.9) == "Medium"


def test_high_possible_reads_the_top_of_the_band_against_the_same_threshold():
    assert high_possible("BPH", "Vegetative", 19.9) is False
    assert high_possible("BPH", "Vegetative", 20.0) is True
    assert high_possible("BPH", "Reproductive", 10.0) is True  # stricter stage threshold
    assert high_possible("RSB", "Vegetative", 5.0) is True
    assert high_possible("BPH", "Vegetative", None) is None  # no band, no warning

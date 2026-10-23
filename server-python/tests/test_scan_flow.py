"""The scan flow end to end with the models stubbed, so each branch is tested
without needing real photos: planthoppers found, no insect but stem-borer
damage, nothing found, and the area/size maths."""

import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.preprocessing.photo_footprint import estimate_field_size_ha, ground_area_by_cell
from app.routers import inference as inf

DAMAGED = [[8, 9, 7], [9, 10, 8], [6, 7, 9]]
MILD = [[1, 0, 0], [0.5, 2, 0], [0, 0, 0.5]]


def _jpeg(extra: bytes = b"", focal35: int | None = None) -> bytes:
    buf = io.BytesIO()
    exif = Image.Exif()
    if focal35:
        exif[0x8769] = {0xA405: focal35}
    Image.new("RGB", (640, 480), (60, 120, 40)).save(buf, "JPEG", exif=exif)
    return buf.getvalue() + extra


def _classifier(label):
    return SimpleNamespace(
        label=label, unidentified=False, pest_scores={}, grid_tiles=None, grid_count=None,
        confidence=0.97 if label else None, risk_level="High" if label else None,
        pests_detected=[label] if label else [],
    )


def _scan(client, **fields):
    return client.post("/api/inference/image", files={"file": ("a.jpg", _jpeg(), "image/jpeg")}, data=fields)


@pytest.fixture
def stub(monkeypatch):
    def set_models(label, cells):
        monkeypatch.setattr(inf.resnet_classifier, "predict", lambda path: _classifier(label))
        monkeypatch.setattr(inf.resnet_regressors, "predict_grid", lambda *a, **k: cells)
    return set_models


def test_planthopper_photo_is_counted_and_forecast(client, monkeypatch, stub):
    stub("BPH", None)
    body = _scan(client, municipality="Arayat", growth_stage="Tillering").json()
    assert body["status"] == "ok" and body["pest_detected"] == "BPH"
    assert body["estimated_count"] is not None
    assert body["field_assessment"] is None  # no BPH field model
    assert body["forecast_reflects_this_photo"] and len(body["forecast"]["points"]) == 13


def test_no_insect_but_damage_is_flagged_rsb_with_trajectory(client, stub):
    stub(None, DAMAGED)
    body = _scan(client, municipality="Arayat", growth_stage="Flowering").json()
    assert body["status"] == "damage_detected" and body["pest_detected"] == "RSB"
    fa = body["field_assessment"]
    assert fa["pct_affected"] > 0 and fa["cells_affected_pct"] == 100
    assert body["forecast"]["points"][0]["unit"] == "pct_damage"
    assert body["forecast_reflects_this_photo"]


def test_mild_or_no_damage_is_not_flagged(client, stub):
    stub(None, MILD)
    assert _scan(client).json()["status"] == "no_pest_detected"


def test_area_follows_damage_share_not_whole_cells(client, stub):
    stub(None, DAMAGED)
    fa = _scan(client).json()["field_assessment"]
    # ~8% of the photo is damaged: the damaged area must be far below the area of the cells it touches.
    assert fa["affected_area_m2"] < fa["spread_area_m2"] <= fa["visible_area_m2"] + 0.1
    assert fa["affected_area_m2"] == pytest.approx(fa["visible_area_m2"] * fa["pct_affected"] / 100, rel=0.5)
    assert fa["affected_area_m2_low"] < fa["affected_area_m2"] < fa["affected_area_m2_high"]


def test_entered_field_size_overrides_and_scales_hectares(client, stub):
    stub(None, DAMAGED)
    fa = _scan(client, field_size_ha="2").json()["field_assessment"]
    assert fa["field_size_source"] == "entered"
    assert fa["affected_hectares"] == round(fa["pct_affected"] / 100 * 2, 4)


def test_fake_image_is_rejected_with_422(client):
    for path, data in (("/api/inference/image", {}), ("/api/inference/field-assessment", {"pest": "RSB"})):
        res = client.post(path, files={"file": ("a.jpg", b"not an image", "image/jpeg")}, data=data)
        assert res.status_code == 422


def test_drone_photo_size_is_read_from_metadata(tmp_path):
    xmp = b'<x:xmpmeta drone-dji:RelativeAltitude="+100.0" drone-dji:GimbalPitchDegree="-90.0"></x:xmpmeta>'
    drone = tmp_path / "drone.jpg"
    drone.write_bytes(_jpeg(xmp, focal35=24))
    assert estimate_field_size_ha(drone) == 1.5  # 150 m x 100 m
    plain = tmp_path / "plain.jpg"
    plain.write_bytes(_jpeg(focal35=24))
    assert estimate_field_size_ha(plain) is None
    tilted = tmp_path / "tilted.jpg"
    tilted.write_bytes(_jpeg(xmp.replace(b"-90.0", b"-30.0"), focal35=24))
    assert estimate_field_size_ha(tilted) is None  # oblique shot: no footprint guess


def test_ground_area_grows_towards_the_far_rows(tmp_path):
    photo = tmp_path / "p.jpg"
    photo.write_bytes(_jpeg(focal35=26))
    areas = ground_area_by_cell(photo, 3, 3)
    assert areas[0][0] > areas[1][0] > areas[2][0] > 0  # row 0 is the farthest


def test_report_photo_with_only_damage_is_attributed_to_rsb(client, stub, monkeypatch):
    """A farmer's report photo with no insect but stem-borer damage records RSB and the
    severity as an AI suggestion (not as the verified value)."""
    from app.routers import reports

    saved = []
    monkeypatch.setattr(reports.reports_store, "create_report", saved.append)
    monkeypatch.setattr(reports.reports_store, "count_recent_similar_reports", lambda *a, **k: 0)
    stub(None, DAMAGED)
    res = client.post(
        "/api/reports",
        files={"file": ("a.jpg", _jpeg(), "image/jpeg")},
        data={
            "pest_type": "Rice Stem Borer (Aksip o Atip)", "severity": "Medium", "province": "Nueva Ecija",
            "municipality": "Arayat", "date_spotted": "2026-10-20", "username": "pytest-farmer",
        },
    )
    assert res.status_code in (200, 201), res.text
    record = saved[0]
    assert record.ai_pest_detected == "RSB"
    assert record.ai_suggested_damage_pct and record.ai_suggested_damage_pct > 0
    assert record.estimated_value is None


def test_damage_outranks_the_unknown_insect_detector(client, monkeypatch, stub):
    """The unknown-insect detector fires on plant photos, so damage is checked first."""
    stub(None, DAMAGED)
    unidentified = _classifier(None)
    unidentified.unidentified = True
    monkeypatch.setattr(inf.resnet_classifier, "predict", lambda path: unidentified)
    assert _scan(client).json()["status"] == "damage_detected"
    monkeypatch.setattr(inf.resnet_regressors, "predict_grid", lambda *a, **k: [[0.0] * 3] * 3)
    assert _scan(client).json()["status"] == "unidentified_pest_detected"


def test_detector_second_opinion_only_for_small_photos():
    from app.models.planthopper_detector import Detection, PlanthopperDetector

    box = lambda score: [Detection(0, 0, 10, 10, score)]
    second = PlanthopperDetector.second_opinion
    assert second(box(0.65), 0.2, tiled=False)  # near-miss classifier + clear box
    assert not second(box(0.65), 0.05, tiled=False)  # classifier far from a hit
    assert not second(box(0.5), 0.2, tiled=False)  # box not clear enough
    assert not second(box(0.95), 0.9, tiled=True)  # tiled photo: classifier score means something else
    assert not second(None, 0.9, tiled=False) and not second([], 0.9, tiled=False)


def test_small_photo_near_miss_becomes_bph_with_a_clear_box(client, monkeypatch, stub):
    from app.models.planthopper_detector import Detection

    stub(None, None)
    from app.models.resnet_model import ResnetPrediction

    near_miss = ResnetPrediction(label=None, confidence=0.3, risk_level="Low", pest_scores={"BPH": 0.3, "RSB": 0.0})
    monkeypatch.setattr(inf.resnet_classifier, "predict", lambda path: near_miss)
    monkeypatch.setattr(inf.planthopper_detector, "detect", lambda path: [Detection(1, 1, 9, 9, 0.7)])
    body = _scan(client).json()
    assert body["status"] == "ok" and body["pest_detected"] == "BPH"
    assert body["estimated_count"] == 1.0  # one box

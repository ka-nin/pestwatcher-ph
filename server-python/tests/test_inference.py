def test_forecast_live_returns_a_known_status(client):
    """Doesn't assert a specific predicted value (that would make this test
    brittle against retraining) — just that the live forecast pipeline runs
    end to end for a real seeded municipality and returns one of its two
    documented statuses (see app/schemas/inference.py's ForecastInferenceResponse)."""
    res = client.get(
        "/api/inference/forecast/live",
        params={"municipality": "Arayat", "pest": "BPH", "growth_stage": "Tillering"},
    )
    assert res.status_code == 200

    body = res.json()
    assert body["status"] in ("ok", "model_not_loaded")
    if body["status"] == "ok":
        assert body["risk_level"] in ("Low", "Medium", "High")
        assert body["predicted_value"] is not None


def test_forecast_live_rejects_unknown_municipality(client):
    res = client.get(
        "/api/inference/forecast/live",
        params={"municipality": "Not A Real Town", "pest": "BPH", "growth_stage": "Tillering"},
    )
    assert res.status_code == 404


def _jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (60, 140, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def test_field_assessment_returns_a_consistent_result(client):
    """Whether or not a field model is installed, the endpoint returns one of
    its documented statuses; when it does produce a result, severity, spread
    and the cell grid agree with each other."""
    res = client.post(
        "/api/inference/field-assessment",
        files={"file": ("field.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"pest": "RSB", "field_size_ha": "2"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("ok", "model_not_loaded")
    if body["status"] == "ok":
        cells = [v for row in body["cell_values"] for v in row]
        assert len(cells) == body["rows"] * body["cols"]
        assert all(v >= 0 for v in cells)
        assert 0 <= body["cells_affected_pct"] <= 100
        assert body["affected_hectares"] == round(body["pct_affected"] / 100 * 2, 2)
        assert len(body["cell_has_damage"]) == body["rows"]


def test_field_assessment_rejects_a_non_image(client):
    res = client.post(
        "/api/inference/field-assessment",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
        data={"pest": "RSB"},
    )
    assert res.status_code == 415

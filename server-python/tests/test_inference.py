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

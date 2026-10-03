def test_login_rejects_bad_credentials(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "definitely-not-a-real-account", "password": "wrong"},
    )
    assert res.status_code == 401


def test_login_succeeds_with_real_lgu_credentials(client, lgu_credentials):
    username, password = lgu_credentials
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200

    body = res.json()
    assert body["accessToken"]
    assert body["user"]["username"] == username
    assert body["user"]["accountType"] == "lgu"


def test_patch_report_status_requires_auth(client):
    """Regression test for the auth gap found in app/routers/reports.py's
    update_report_status — this route must reject an unauthenticated
    request, not silently accept it (it used to)."""
    res = client.patch(
        "/api/reports/nonexistent-report-id",
        json={"status": "verified"},
    )
    assert res.status_code == 401

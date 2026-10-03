"""Shared fixtures for the smoke-test suite.

These tests run against the real dev FastAPI app and the real dev Postgres
database (docker compose up -d, from the repo root) — there's no separate
test-database infra at this project's scope. They're intentionally narrow:
a handful of smoke tests that prove the app boots and its core request paths
work end to end, not a full correctness suite.
"""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_CSV = REPO_ROOT / "credentials.txt"


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def lgu_credentials() -> tuple[str, str]:
    """One real seeded LGU technician's (username, password), read from
    credentials.txt at test time rather than hardcoded here — see that
    file for the full seeded account list. Skips (not fails) if the file
    isn't present, so this suite still runs in an environment that doesn't
    have it checked out."""
    if not CREDENTIALS_CSV.exists():
        pytest.skip(f"{CREDENTIALS_CSV} not found — skipping tests that need a real login")

    with CREDENTIALS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            if row["Role"].strip() == "LGU_Tech":
                return row["Username"].strip(), row["Password"].strip()

    pytest.skip("No LGU_Tech row found in credentials.txt")

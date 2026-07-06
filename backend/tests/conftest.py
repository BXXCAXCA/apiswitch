import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).parent / "test_apiswitch.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["APISWITCH_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from apiswitch.app import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def gateway_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/tokens",
        json={"name": "pytest-gateway", "scopes": ["gateway:invoke"]},
    )
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}

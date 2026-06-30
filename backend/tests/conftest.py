from fastapi.testclient import TestClient
import pytest

from apiswitch.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)

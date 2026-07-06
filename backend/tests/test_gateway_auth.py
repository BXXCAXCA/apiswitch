from datetime import datetime, timedelta


def _create_token(client, name="auth-test", scopes=None, expires_at=None):
    payload = {"name": name, "scopes": scopes or ["gateway:invoke"]}
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    response = client.post("/api/admin/tokens", json=payload)
    assert response.status_code == 200
    return response.json()


def test_gateway_requires_bearer_token(client):
    response = client.get("/v1/models")
    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "missing_api_token"


def test_gateway_rejects_invalid_token(client):
    response = client.get("/v1/models", headers={"Authorization": "Bearer ask_invalid"})
    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "invalid_api_token"


def test_gateway_rejects_disabled_token(client):
    created = _create_token(client, "disabled-token")
    client.patch(f"/api/admin/tokens/{created['id']}", json={"enabled": False})
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {created['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "api_token_disabled"


def test_gateway_rejects_expired_token(client):
    created = _create_token(client, "expired-token", expires_at=datetime.utcnow() - timedelta(days=1))
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {created['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "api_token_expired"


def test_gateway_rejects_token_without_invoke_scope(client):
    created = _create_token(client, "read-only-token", scopes=["gateway:read"])
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {created['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "insufficient_scope"


def test_gateway_updates_last_used_at(client):
    created = _create_token(client, "last-used-token")
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {created['token']}"})
    assert response.status_code == 200

    listed = client.get("/api/admin/tokens").json()
    item = next(token for token in listed if token["id"] == created["id"])
    assert item["last_used_at"] is not None

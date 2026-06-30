def test_dashboard_summary(client):
    response = client.get("/api/admin/dashboard/summary")
    assert response.status_code == 200
    assert "requests_total" in response.json()


def test_providers(client):
    response = client.get("/api/admin/providers")
    assert response.status_code == 200
    assert response.json()[0]["type"] == "mock"


def test_provider_crud(client):
    created = client.post(
        "/api/admin/providers",
        json={
            "name": "mock-extra",
            "type": "mock",
            "base_url": "mock://extra",
            "api_key": "secret-test-key",
            "enabled": True,
            "timeout_seconds": 90,
        },
    )
    assert created.status_code == 200
    provider = created.json()
    assert provider["name"] == "mock-extra"
    assert provider["api_key_configured"] is True
    assert "secret-test-key" not in str(provider)

    updated = client.patch(
        f"/api/admin/providers/{provider['id']}",
        json={"enabled": False, "timeout_seconds": 60},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["timeout_seconds"] == 60

    deleted = client.delete(f"/api/admin/providers/{provider['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_openai_provider_without_key_reports_connection_failure(client):
    provider = client.post(
        "/api/admin/providers",
        json={
            "name": "openai-no-key",
            "type": "openai",
            "base_url": "https://api.openai.com/v1",
            "enabled": True,
            "timeout_seconds": 30,
        },
    ).json()

    tested = client.post(f"/api/admin/providers/{provider['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["ok"] is False
    assert "Missing OpenAI API key" in tested.json()["message"]


def test_provider_test_and_model_discovery(client):
    provider = client.get("/api/admin/providers").json()[0]

    tested = client.post(f"/api/admin/providers/{provider['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    discovered = client.post(f"/api/admin/providers/{provider['id']}/discover-models")
    assert discovered.status_code == 200
    body = discovered.json()
    assert body["provider_name"] == "mock-main"
    assert len(body["models"]) >= 1

    provider_models = client.get(f"/api/admin/providers/{provider['id']}/models")
    assert provider_models.status_code == 200
    assert any(item["model_name"] == "code-best" for item in provider_models.json())


def test_unified_model_and_candidate_crud(client):
    provider = client.post(
        "/api/admin/providers",
        json={
            "name": "mock-candidate-provider",
            "type": "mock",
            "base_url": "mock://candidate",
            "enabled": True,
            "timeout_seconds": 120,
        },
    ).json()

    created_model = client.post(
        "/api/admin/unified-models",
        json={
            "name": "test-model-route",
            "description": "test route",
            "enabled": True,
            "capabilities": ["text"],
        },
    )
    assert created_model.status_code == 200
    model = created_model.json()

    created_candidate = client.post(
        f"/api/admin/unified-models/{model['id']}/candidates",
        json={
            "provider_id": provider["id"],
            "upstream_model": "mock-chat",
            "manual_priority": 80,
            "enabled": True,
            "capabilities": ["text"],
        },
    )
    assert created_candidate.status_code == 200
    candidate = created_candidate.json()
    assert candidate["provider_name"] == "mock-candidate-provider"

    listed = client.get(f"/api/admin/unified-models/{model['id']}/candidates")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/admin/unified-models/{model['id']}/candidates/{candidate['id']}",
        json={"manual_priority": 90},
    )
    assert updated.status_code == 200
    assert updated.json()["manual_priority"] == 90


def test_router_health(client):
    response = client.get("/api/admin/router-health")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    first = body["items"][0]
    assert first["unified_model"] == "code-best"
    assert first["circuit_state"] in {"closed", "open", "half_open"}
    assert "available" in first
    assert "failure_threshold" in first
    assert "cooldown_seconds" in first

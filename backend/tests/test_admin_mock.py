def test_dashboard_summary(client):
    response = client.get("/api/admin/dashboard/summary")
    assert response.status_code == 200
    assert "requests_total" in response.json()


def test_providers(client):
    response = client.get("/api/admin/providers")
    assert response.status_code == 200
    assert response.json()[0]["type"] == "mock"


def test_router_health(client):
    response = client.get("/api/admin/router-health")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["items"][0]["unified_model"] == "code-best"

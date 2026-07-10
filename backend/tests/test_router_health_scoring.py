def test_router_health_exposes_score_breakdown(client):
    response = client.get("/api/admin/router-health")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["score_breakdown"]["mode"] == "extended"
    assert "health" in item["score_breakdown"]["factors"]
    assert "cost" in item["score_breakdown"]["factors"]
    assert "quota" in item["score_breakdown"]["factors"]
    assert "failure" in item["score_breakdown"]["penalties"]

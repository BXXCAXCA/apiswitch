def _create_connection_and_node(client, provider_id: int) -> tuple[dict, dict]:
    connection_response = client.post(
        f"/api/admin/providers/{provider_id}/connections",
        json={
            "name": "route-account",
            "auth_type": "api_key",
            "credential": "route-secret",
            "enabled": True,
            "priority": 200,
        },
    )
    assert connection_response.status_code == 200
    connection = connection_response.json()
    node_response = client.post(
        f"/api/admin/providers/{provider_id}/nodes",
        json={
            "name": "route-node",
            "connection_id": connection["id"],
            "base_url": "mock://route-node",
            "enabled": True,
            "weight": 200,
            "capabilities": ["text"],
        },
    )
    assert node_response.status_code == 200
    return connection, node_response.json()


def test_candidate_can_route_through_specific_connection_and_node(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    unified_model = next(item for item in client.get("/api/admin/unified-models").json() if item["name"] == "code-best")
    client.patch(f"/api/admin/unified-models/{unified_model['id']}", json={"routing_mode": "static"})
    connection, node = _create_connection_and_node(client, provider["id"])
    for existing_candidate in unified_model["candidates"]:
        disabled = client.patch(
            f"/api/admin/unified-models/{unified_model['id']}/candidates/{existing_candidate['id']}",
            json={"enabled": False},
        )
        assert disabled.status_code == 200

    candidate_response = client.post(
        f"/api/admin/unified-models/{unified_model['id']}/candidates",
        json={
            "provider_id": provider["id"],
            "provider_connection_id": connection["id"],
            "provider_node_id": node["id"],
            "upstream_model": "mock-chat",
            "manual_priority": 1000,
            "capabilities": ["text"],
        },
    )
    assert candidate_response.status_code == 200
    candidate = candidate_response.json()
    assert candidate["provider_connection_id"] == connection["id"]
    assert candidate["provider_node_id"] == node["id"]

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    routing = response.json()["apiswitch"]
    assert routing["score_breakdown"]["provider_connection_id"] == connection["id"]
    assert routing["score_breakdown"]["provider_node_id"] == node["id"]

    logs = client.get("/api/admin/logs").json()["items"]
    assert logs[0]["provider_connection_id"] == connection["id"]
    assert logs[0]["provider_node_id"] == node["id"]


def test_candidate_rejects_node_without_its_connection(client):
    provider = client.get("/api/admin/providers").json()[0]
    unified_model = next(item for item in client.get("/api/admin/unified-models").json() if item["name"] == "code-best")
    _, node = _create_connection_and_node(client, provider["id"])

    response = client.post(
        f"/api/admin/unified-models/{unified_model['id']}/candidates",
        json={
            "provider_id": provider["id"],
            "provider_node_id": node["id"],
            "upstream_model": "mock-node-only",
        },
    )
    assert response.status_code == 422


def test_candidate_rejects_unknown_connection(client):
    provider = client.get("/api/admin/providers").json()[0]
    unified_model = next(item for item in client.get("/api/admin/unified-models").json() if item["name"] == "code-best")
    response = client.post(
        f"/api/admin/unified-models/{unified_model['id']}/candidates",
        json={
            "provider_id": provider["id"],
            "provider_connection_id": 999999,
            "upstream_model": "mock-unknown-account",
        },
    )
    assert response.status_code == 404

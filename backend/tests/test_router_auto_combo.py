def test_auto_mode_materializes_enabled_connection_node_targets(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    unified = next(item for item in client.get("/api/admin/unified-models").json() if item["name"] == "code-best")
    updated = client.patch(
        f"/api/admin/unified-models/{unified['id']}",
        json={"routing_mode": "auto", "category": "coding", "preferred_tier": "reliable"},
    )
    assert updated.status_code == 200
    assert updated.json()["routing_mode"] == "auto"
    assert updated.json()["category"] == "coding"

    connection = client.post(
        f"/api/admin/providers/{provider['id']}/connections",
        json={"name": "auto-account", "auth_type": "api_key", "credential": "auto-secret", "priority": 50},
    ).json()
    node = client.post(
        f"/api/admin/providers/{provider['id']}/nodes",
        json={
            "name": "auto-node",
            "connection_id": connection["id"],
            "base_url": "mock://auto-node",
            "weight": 60,
            "capabilities": ["text"],
        },
    ).json()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200

    candidates = client.get(f"/api/admin/unified-models/{unified['id']}/candidates").json()
    auto_candidate = next(
        item
        for item in candidates
        if item["provider_connection_id"] == connection["id"] and item["provider_node_id"] == node["id"]
    )
    assert auto_candidate["upstream_model"] == "mock-chat"


def test_auto_mode_excludes_expired_connection(client, gateway_headers):
    from datetime import datetime, timedelta

    provider = client.get("/api/admin/providers").json()[0]
    unified = next(item for item in client.get("/api/admin/unified-models").json() if item["name"] == "code-best")
    client.patch(f"/api/admin/unified-models/{unified['id']}", json={"routing_mode": "auto"})
    expired = client.post(
        f"/api/admin/providers/{provider['id']}/connections",
        json={
            "name": "expired-account",
            "auth_type": "api_key",
            "credential": "expired-secret",
            "expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
        },
    )
    assert expired.status_code == 200

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    candidates = client.get(f"/api/admin/unified-models/{unified['id']}/candidates").json()
    assert not any(item["provider_connection_id"] == expired.json()["id"] for item in candidates)


def test_combo_round_robin_rotates_between_explicit_candidates(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    unified = client.post(
        "/api/admin/unified-models",
        json={
            "name": "combo-round-robin",
            "capabilities": ["text"],
            "routing_mode": "combo",
            "combo_strategy": "round_robin",
        },
    ).json()
    for upstream_model in ("mock-a", "mock-b"):
        created = client.post(
            f"/api/admin/unified-models/{unified['id']}/candidates",
            json={
                "provider_id": provider["id"],
                "upstream_model": upstream_model,
                "capabilities": ["text"],
            },
        )
        assert created.status_code == 200

    first = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "combo-round-robin", "messages": [{"role": "user", "content": "one"}]},
    )
    second = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "combo-round-robin", "messages": [{"role": "user", "content": "two"}]},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["apiswitch"]["upstream_model"] != second.json()["apiswitch"]["upstream_model"]
    assert first.json()["apiswitch"]["score_breakdown"]["combo_strategy"] == "round_robin"


def test_combo_cost_optimized_prefers_lowest_priced_candidate(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    unified = client.post(
        "/api/admin/unified-models",
        json={
            "name": "combo-cheap",
            "capabilities": ["text"],
            "routing_mode": "combo",
            "combo_strategy": "cost_optimized",
        },
    ).json()
    for upstream_model in ("mock-expensive", "mock-cheap"):
        client.post(
            f"/api/admin/unified-models/{unified['id']}/candidates",
            json={"provider_id": provider["id"], "upstream_model": upstream_model, "capabilities": ["text"]},
        )
    for model_name, price in (("mock-expensive", 9.0), ("mock-cheap", 1.0)):
        client.post(
            "/api/admin/accounting/pricing",
            json={"provider_id": provider["id"], "model_name": model_name, "input_cost_per_million": price, "output_cost_per_million": price},
        )
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "combo-cheap", "messages": [{"role": "user", "content": "cheap"}]},
    )
    assert response.status_code == 200
    assert response.json()["apiswitch"]["upstream_model"] == "mock-cheap"

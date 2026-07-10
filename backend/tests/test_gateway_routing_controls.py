def _ensure_mock_pricing(client):
    provider = client.get("/api/admin/providers").json()[0]
    response = client.post(
        "/api/admin/accounting/pricing",
        json={
            "provider_id": provider["id"],
            "model_name": "mock-chat",
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 2.0,
            "currency": "USD",
        },
    )
    assert response.status_code == 200


def test_chat_request_controls_and_session_affinity(client, gateway_headers):
    _ensure_mock_pricing(client)
    headers = {
        **gateway_headers,
        "X-APISwitch-Tier": "fast",
        "X-APISwitch-Budget": "0.01",
        "X-APISwitch-Session": "conversation-123",
    }

    first = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert first.status_code == 200
    assert first.json()["apiswitch"]["request_controls"]["tier"] == "fast"
    assert first.json()["apiswitch"]["request_controls"]["budget"] == 0.01

    second = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "again"}]},
    )
    assert second.status_code == 200
    assert second.json()["apiswitch"]["score_breakdown"]["session_affinity"] is True


def test_request_budget_filters_candidate(client, gateway_headers):
    _ensure_mock_pricing(client)
    response = client.post(
        "/v1/chat/completions",
        headers={**gateway_headers, "X-APISwitch-Budget": "0.000001"},
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "no_available_candidate"
    assert "filtered by request budget" in response.json()["detail"]["message"]


def test_invalid_routing_controls_return_400(client, gateway_headers):
    invalid_tier = client.post(
        "/v1/chat/completions",
        headers={**gateway_headers, "X-APISwitch-Tier": "turbo"},
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert invalid_tier.status_code == 400
    assert invalid_tier.json()["detail"]["type"] == "invalid_routing_control"

    invalid_budget = client.post(
        "/v1/chat/completions",
        headers={**gateway_headers, "X-APISwitch-Budget": "0"},
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert invalid_budget.status_code == 400
    assert invalid_budget.json()["detail"]["type"] == "invalid_routing_control"

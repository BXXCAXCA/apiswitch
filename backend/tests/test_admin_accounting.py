def test_pricing_usage_history_and_summary(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]

    pricing = client.post(
        "/api/admin/accounting/pricing",
        json={
            "provider_id": provider["id"],
            "model_name": "mock-chat",
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 2.0,
            "currency": "USD",
        },
    )
    assert pricing.status_code == 200

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert response.json()["apiswitch"]["estimated_cost"] == 0.000003

    usage = client.get("/api/admin/accounting/usage")
    assert usage.status_code == 200
    item = usage.json()[0]
    assert item["unified_model"] == "code-best"
    assert item["upstream_model"] == "mock-chat"
    assert item["input_tokens"] == 1
    assert item["output_tokens"] == 1
    assert item["estimated_cost"] == 0.000003
    assert item["api_token_id"] is not None

    summary = client.get("/api/admin/accounting/usage/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["request_count"] >= 1
    assert body["input_tokens"] >= 1
    assert body["output_tokens"] >= 1
    assert body["priced_request_count"] >= 1
    assert body["estimated_cost"] >= 0.000003

    logs = client.get("/api/admin/logs").json()["items"]
    matching = next(item for item in logs if item["request_id"] == usage.json()[0]["request_id"])
    assert matching["estimated_cost"] == 0.000003


def test_quota_snapshot_for_provider_connection(client):
    provider = client.get("/api/admin/providers").json()[0]
    connection = client.post(
        f"/api/admin/providers/{provider['id']}/connections",
        json={
            "name": "quota-account",
            "auth_type": "api_key",
            "credential": "secret",
            "enabled": True,
            "priority": 100,
        },
    ).json()

    created = client.post(
        "/api/admin/accounting/quota-snapshots",
        json={
            "provider_connection_id": connection["id"],
            "remaining_requests": 1000,
            "remaining_tokens": 500000,
            "remaining_credit": 9.5,
            "raw": {"source": "manual-test"},
        },
    )
    assert created.status_code == 200
    assert created.json()["remaining_credit"] == 9.5

    listed = client.get(
        "/api/admin/accounting/quota-snapshots",
        params={"provider_connection_id": connection["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["remaining_tokens"] == 500000


def test_model_pricing_crud(client):
    created = client.post(
        "/api/admin/accounting/pricing",
        json={
            "provider_id": None,
            "model_name": "global-model",
            "input_cost_per_million": 0.5,
            "output_cost_per_million": 1.5,
        },
    )
    assert created.status_code == 200
    pricing_id = created.json()["id"]

    updated = client.patch(
        f"/api/admin/accounting/pricing/{pricing_id}",
        json={"output_cost_per_million": 2.0},
    )
    assert updated.status_code == 200
    assert updated.json()["output_cost_per_million"] == 2.0

    deleted = client.delete(f"/api/admin/accounting/pricing/{pricing_id}")
    assert deleted.status_code == 200

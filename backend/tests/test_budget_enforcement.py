def _add_pricing(client, provider_id: int, model_name: str, price: float) -> None:
    response = client.post(
        "/api/admin/accounting/pricing",
        json={
            "provider_id": provider_id,
            "model_name": model_name,
            "input_cost_per_million": price,
            "output_cost_per_million": price,
        },
    )
    assert response.status_code == 200


def test_reject_budget_blocks_gateway_request(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    _add_pricing(client, provider["id"], "mock-chat", 1.0)
    budget = client.post(
        "/api/admin/budgets",
        json={
            "name": "hard global cap",
            "scope": "global",
            "monthly_limit": 0,
            "spent_amount": 0,
            "enforcement_action": "reject",
        },
    )
    assert budget.status_code == 200
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "blocked"}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "budget_exceeded"
    client.patch(f"/api/admin/budgets/{budget.json()['id']}", json={"enabled": False})


def test_budget_accumulates_actual_estimated_cost(client, gateway_headers):
    provider = client.get("/api/admin/providers").json()[0]
    _add_pricing(client, provider["id"], "mock-chat", 1.0)
    created = client.post(
        "/api/admin/budgets",
        json={"name": "tracked", "scope": "global", "monthly_limit": 10, "enforcement_action": "warn_only"},
    )
    assert created.status_code == 200
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "charge"}]},
    )
    assert response.status_code == 200
    budget = next(item for item in client.get("/api/admin/budgets").json() if item["id"] == created.json()["id"])
    assert budget["spent_amount"] > 0

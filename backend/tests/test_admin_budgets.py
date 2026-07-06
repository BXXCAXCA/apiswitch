def test_budget_crud(client):
    created = client.post(
        "/api/admin/budgets",
        json={
            "name": "global-monthly",
            "scope": "global",
            "scope_id": None,
            "monthly_limit": 100.0,
            "currency": "USD",
            "enabled": True,
            "spent_amount": 50.0,
            "alert_threshold_percent": 80,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "global-monthly"
    assert body["usage_percent"] == 50.0
    assert body["alert_triggered"] is False

    listed = client.get("/api/admin/budgets")
    assert listed.status_code == 200
    assert any(item["name"] == "global-monthly" for item in listed.json())

    updated = client.patch(
        f"/api/admin/budgets/{body['id']}",
        json={"spent_amount": 90.0, "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["usage_percent"] == 90.0
    assert updated.json()["alert_triggered"] is True

    deleted = client.delete(f"/api/admin/budgets/{body['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_budget_without_limit_has_no_usage_percent(client):
    created = client.post(
        "/api/admin/budgets",
        json={
            "name": "unlimited-token-budget",
            "scope": "api_token",
            "scope_id": "token-1",
            "monthly_limit": None,
            "currency": "USD",
            "enabled": True,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["usage_percent"] is None
    assert body["alert_triggered"] is False

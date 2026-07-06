def test_settings_are_persistent(client):
    initial = client.get("/api/admin/settings")
    assert initial.status_code == 200
    assert initial.json()["settings"]["default_unified_model"] == "code-best"

    updated = client.patch(
        "/api/admin/settings",
        json={
            "default_timeout_seconds": 90,
            "request_log_retention_days": 14,
            "record_full_request": True,
            "default_provider_type": "openai",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["settings"]["default_timeout_seconds"] == 90
    assert body["settings"]["request_log_retention_days"] == 14
    assert body["settings"]["record_full_request"] is True
    assert body["settings"]["default_provider_type"] == "openai"

    reloaded = client.get("/api/admin/settings")
    assert reloaded.status_code == 200
    assert reloaded.json()["settings"]["default_timeout_seconds"] == 90
    assert reloaded.json()["raw"]["default_provider_type"] == "openai"

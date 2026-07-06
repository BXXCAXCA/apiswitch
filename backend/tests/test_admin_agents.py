def test_agent_config_crud_and_mock_path_check(client):
    created = client.post(
        "/api/admin/agents",
        json={
            "agent_type": "claude-code",
            "config_path": "mock://claude-code/settings.json",
            "last_backup_path": None,
            "enabled": True,
            "notes": "main coding agent",
            "settings": {"profile": "default"},
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["agent_type"] == "claude-code"
    assert body["enabled"] is True
    assert body["notes"] == "main coding agent"
    assert body["settings"]["profile"] == "default"
    assert body["config_exists"] is True
    assert body["backup_configured"] is False

    listed = client.get("/api/admin/agents")
    assert listed.status_code == 200
    assert listed.json()[0]["agent_type"] == "claude-code"

    checked = client.post(f"/api/admin/agents/{body['id']}/check")
    assert checked.status_code == 200
    assert checked.json()["ok"] is True

    updated = client.patch(
        f"/api/admin/agents/{body['id']}",
        json={"enabled": False, "last_backup_path": "mock://backup/claude-code.json"},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["backup_configured"] is True

    deleted = client.delete(f"/api/admin/agents/{body['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_agent_config_missing_path_check(client):
    created = client.post(
        "/api/admin/agents",
        json={
            "agent_type": "gemini-cli",
            "config_path": "/definitely/missing/gemini/settings.json",
            "enabled": True,
        },
    ).json()

    checked = client.post(f"/api/admin/agents/{created['id']}/check")
    assert checked.status_code == 200
    assert checked.json()["ok"] is False
    assert checked.json()["config_exists"] is False

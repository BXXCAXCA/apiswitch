import json
from pathlib import Path


def test_claude_code_profile_preview_and_write(client, monkeypatch, tmp_path):
    profiles_root = tmp_path / "claude-profiles"
    monkeypatch.setenv("APISWITCH_CLAUDE_CONFIG_ROOT", str(profiles_root))

    payload = {
        "profile_name": "apiswitch-test",
        "base_url": "http://127.0.0.1:8080/v1",
        "model": "code-best",
        "effort_level": "high",
        "max_output_tokens": 8192,
        "auto_compact_window": 100000,
    }

    preview = client.post("/api/admin/agents/claude-code/write", json={**payload, "dry_run": True})
    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["written"] is False
    assert preview_body["settings"]["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8080"
    assert "ANTHROPIC_AUTH_TOKEN" not in preview_body["settings"]["env"]
    assert not Path(preview_body["settings_path"]).exists()

    written = client.post("/api/admin/agents/claude-code/write", json={**payload, "dry_run": False})
    assert written.status_code == 200
    body = written.json()
    assert body["written"] is True

    settings_path = Path(body["settings_path"])
    assert settings_path.exists()
    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    assert stored["model"] == "code-best"
    assert stored["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8080"
    assert stored["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"
    assert "ANTHROPIC_AUTH_TOKEN" not in stored["env"]

    rewritten = client.post(
        "/api/admin/agents/claude-code/write",
        json={**payload, "model": "chat-fast", "dry_run": False},
    )
    assert rewritten.status_code == 200
    backup_path = Path(rewritten.json()["backup_path"])
    assert backup_path.exists()
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    assert backup["model"] == "code-best"

    agents = client.get("/api/admin/agents")
    assert agents.status_code == 200
    assert any(item["agent_type"] == "claude-code" for item in agents.json())


def test_claude_code_profile_rejects_unsafe_name(client, monkeypatch, tmp_path):
    monkeypatch.setenv("APISWITCH_CLAUDE_CONFIG_ROOT", str(tmp_path / "profiles"))
    response = client.post(
        "/api/admin/agents/claude-code/write",
        json={
            "profile_name": "../escape",
            "base_url": "http://127.0.0.1:8080",
            "model": "code-best",
            "dry_run": False,
        },
    )
    assert response.status_code == 400

import json
import socket
from pathlib import Path

import tomlkit
import yaml
from apiswitch.desktop import _refresh_agents_for_port_change, _select_port


def test_select_port_uses_preferred_port_when_available():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        preferred = probe.getsockname()[1]

    assert _select_port(preferred) == preferred


def test_select_port_avoids_an_existing_windows_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        occupied_port = listener.getsockname()[1]

        selected_port = _select_port(occupied_port)

        assert selected_port != occupied_port
        assert 0 < selected_port <= 65535


def test_port_change_backs_up_and_refreshes_enabled_claude_config(client, tmp_path, monkeypatch):
    model = client.post(
        "/api/admin/unified-models",
        json={"name": "agent-main", "enabled_protocols": ["anthropic_messages"]},
    ).json()
    target = tmp_path / "claude-code.json"
    target.write_text('{"before":true}', encoding="utf-8")
    monkeypatch.setattr(
        "apiswitch.desktop.runtime_info",
        lambda: {"base_url": "http://127.0.0.1:8080", "port": 8080},
    )
    written = client.post(
        "/api/admin/agents/claude-code/write",
        json={"config_path": str(target), "main_model_id": model["id"]},
    )
    assert written.status_code == 200
    first_backup = written.json()["backup_path"]
    assert json.loads(open(first_backup, encoding="utf-8").read()) == {"before": True}

    assert _refresh_agents_for_port_change(
        "http://127.0.0.1:8080", "http://127.0.0.1:53421"
    ) == 1
    refreshed = json.loads(target.read_text(encoding="utf-8"))
    assert refreshed["model"]=="agent-main"
    assert refreshed["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:53421"
    agent = client.get("/api/admin/agents").json()[0]
    assert agent["last_written_base_url"] == "http://127.0.0.1:53421"
    assert agent["last_backup_path"] != first_backup
    assert json.loads(open(agent["last_backup_path"], encoding="utf-8").read())["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8080"
    assert _refresh_agents_for_port_change(
        "http://127.0.0.1:53421", "http://127.0.0.1:53421"
    ) == 0


def test_claude_config_maps_four_unified_models_and_restore_is_atomic(client,tmp_path,monkeypatch):
    models=[]
    for name in ("main","opus","sonnet","haiku"):
        models.append(client.post("/api/admin/unified-models",json={"name":f"agent-{name}","enabled_protocols":["anthropic_messages"]}).json())
    target=tmp_path/"settings.json";target.write_text('{"original":true}',encoding="utf-8")
    monkeypatch.setattr("apiswitch.desktop.runtime_info",lambda:{"base_url":"http://127.0.0.1:8080"})
    payload={"config_path":str(target),"main_model_id":models[0]["id"],"opus_model_id":models[1]["id"],"sonnet_model_id":models[2]["id"],"haiku_model_id":models[3]["id"]}
    preview=client.post("/api/admin/agents/claude-code/preview",json=payload).json()
    assert preview["content"]["model"]=="agent-main"
    assert preview["content"]["env"]=={
        "ANTHROPIC_BASE_URL":"http://127.0.0.1:8080",
        "ANTHROPIC_MODEL":"agent-main",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY":"1",
        "ANTHROPIC_DEFAULT_OPUS_MODEL":"agent-opus",
        "ANTHROPIC_DEFAULT_SONNET_MODEL":"agent-sonnet",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL":"agent-haiku",
    }
    written=client.post("/api/admin/agents/claude-code/write",json=payload).json()
    backup=Path(written["backup_path"]);assert json.loads(backup.read_text(encoding="utf-8"))=={"original":True}
    target.write_text('{"changed":true}',encoding="utf-8")
    restored=client.post("/api/admin/agents/claude-code/restore",json={"config_path":str(target),"backup_path":str(backup)})
    assert restored.status_code==200 and json.loads(target.read_text(encoding="utf-8"))=={"original":True}


def test_agent_write_rejects_path_outside_current_user_profile(client,monkeypatch,tmp_path):
    model=client.post("/api/admin/unified-models",json={"name":"agent-safe","enabled_protocols":["anthropic_messages"]}).json()
    monkeypatch.setenv("USERPROFILE",str(tmp_path/"profile"))
    response=client.post("/api/admin/agents/claude-code/write",json={"config_path":str(tmp_path/"outside"/"settings.json"),"main_model_id":model["id"]})
    assert response.status_code==422


def test_five_agent_adapters_preview_merge_backup_and_write(client, tmp_path, monkeypatch):
    model = client.post(
        "/api/admin/unified-models",
        json={"name": "agent-all", "enabled_protocols": ["openai_chat", "openai_responses", "gemini_v1beta"]},
    ).json()
    monkeypatch.setattr("apiswitch.desktop.runtime_info", lambda: {"base_url": "http://127.0.0.1:8080"})
    targets = {
        "codex": tmp_path / "config.toml",
        "opencode": tmp_path / "opencode.json",
        "openclaw": tmp_path / "openclaw.json",
        "hermes": tmp_path / "config.yaml",
        "gemini-cli": tmp_path / ".env",
    }
    initial = {
        "codex": 'personality = "friendly"\n',
        "opencode": '{"autoupdate":false}',
        "openclaw": '{"gateway":{"port":18789}}',
        "hermes": "terminal:\n  backend: local\n",
        "gemini-cli": "KEEP_ME=yes\n",
    }
    for agent_type, target in targets.items():
        target.write_text(initial[agent_type], encoding="utf-8")
        payload = {"config_path": str(target), "main_model_id": model["id"], "api_token": "ask_agent_secret"}
        preview = client.post(f"/api/admin/agents/{agent_type}/preview", json=payload)
        assert preview.status_code == 200, preview.text
        assert "ask_agent_secret" not in preview.json()["content"]
        written = client.post(f"/api/admin/agents/{agent_type}/write", json=payload)
        assert written.status_code == 200, written.text
        assert Path(written.json()["backup_path"]).read_text(encoding="utf-8") == initial[agent_type]

    codex = tomlkit.parse(targets["codex"].read_text(encoding="utf-8"))
    assert codex["personality"] == "friendly" and codex["model"] == "agent-all"
    assert codex["model_providers"]["apiswitch"]["base_url"] == "http://127.0.0.1:8080/v1"
    opencode = json.loads(targets["opencode"].read_text(encoding="utf-8"))
    assert opencode["autoupdate"] is False and opencode["model"] == "apiswitch/agent-all"
    assert opencode["provider"]["apiswitch"]["options"]["apiKey"] == "ask_agent_secret"
    openclaw = json.loads(targets["openclaw"].read_text(encoding="utf-8"))
    assert openclaw["gateway"]["port"] == 18789
    assert openclaw["agents"]["defaults"]["model"]["primary"] == "apiswitch/agent-all"
    hermes = yaml.safe_load(targets["hermes"].read_text(encoding="utf-8"))
    assert hermes["terminal"]["backend"] == "local" and hermes["model"]["provider"] == "custom"
    gemini = targets["gemini-cli"].read_text(encoding="utf-8")
    assert "KEEP_ME=yes" in gemini and "GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:8080" in gemini
    assert "GEMINI_MODEL=agent-all" in gemini and "GEMINI_API_KEY=ask_agent_secret" in gemini

    assert _refresh_agents_for_port_change("http://127.0.0.1:8080", "http://127.0.0.1:53421") == 5
    assert "http://127.0.0.1:53421" in targets["gemini-cli"].read_text(encoding="utf-8")
    assert "http://127.0.0.1:53421/v1" in targets["codex"].read_text(encoding="utf-8")


def test_agent_adapter_rejects_a_model_without_required_protocol(client, tmp_path, monkeypatch):
    model = client.post(
        "/api/admin/unified-models",
        json={"name": "chat-only", "enabled_protocols": ["openai_chat"]},
    ).json()
    monkeypatch.setattr("apiswitch.desktop.runtime_info", lambda: {"base_url": "http://127.0.0.1:8080"})
    response = client.post(
        "/api/admin/agents/gemini-cli/preview",
        json={"config_path": str(tmp_path / ".env"), "main_model_id": model["id"]},
    )
    assert response.status_code == 422
    assert "gemini_v1beta" in response.json()["detail"]["message"]

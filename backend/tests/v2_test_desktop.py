import json
import socket
from pathlib import Path

import tomlkit
import yaml
from apiswitch import __version__
from apiswitch.db.models import AgentConfig
from apiswitch.db.session import SessionLocal
from apiswitch.desktop import DesktopTray, _clear_runtime, _refresh_agents_for_port_change, _repair_startup_command, _select_port, _stop_backend_server, _write_runtime, is_startup_enabled


def test_runtime_file_uses_package_version(tmp_path, monkeypatch):
    monkeypatch.setattr("apiswitch.desktop._runtime_dir", lambda: tmp_path)

    _write_runtime(54321)

    assert json.loads((tmp_path / "runtime.json").read_text(encoding="utf-8"))["version"] == __version__


def test_runtime_file_cleanup_only_removes_its_own_marker(tmp_path, monkeypatch):
    monkeypatch.setattr("apiswitch.desktop._runtime_dir", lambda: tmp_path)
    runtime = tmp_path / "runtime.json"
    runtime.write_text('{"pid":98765}', encoding="utf-8")

    _clear_runtime(expected_pid=12345)
    assert runtime.is_file()

    _clear_runtime(expected_pid=98765)
    assert not runtime.exists()


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


def test_minimizing_keeps_native_taskbar_restore_available():
    tray = object.__new__(DesktopTray)
    hide_calls = []
    tray.window = type("Window", (), {"hide": lambda self: hide_calls.append(True)})()
    tray.on_minimized()
    assert hide_calls == []


def test_window_close_hides_to_tray_and_explains_how_to_exit(monkeypatch):
    tray = object.__new__(DesktopTray)
    tray.exiting = False
    hidden=[];notifications=[]
    tray.window = type("Window", (), {"hide": lambda self: hidden.append(True)})()
    tray.icon = type("Icon", (), {"notify": lambda self, message, title: notifications.append((message,title))})()

    class ImmediateThread:
        def __init__(self,target,**_kwargs):self.target=target
        def start(self):self.target()

    monkeypatch.setattr("apiswitch.desktop.threading.Thread",ImmediateThread)

    assert tray.on_closing() is False
    assert tray.exiting is False
    assert hidden==[True]
    assert notifications and "托盘" in notifications[0][0] and "退出" in notifications[0][0]


def test_enabled_startup_entry_is_recognized_and_repaired_after_upgrade(monkeypatch):
    writes=[]
    monkeypatch.setattr("apiswitch.desktop._read_startup_command",lambda:'C:\\old\\APISwitch-v0.1.14.exe --background')
    monkeypatch.setattr("apiswitch.desktop._startup_command",lambda:'C:\\new\\APISwitch-v0.1.15.exe --background')
    monkeypatch.setattr("apiswitch.desktop._write_startup_command",lambda value:writes.append(value))

    assert is_startup_enabled() is True
    assert _repair_startup_command() is True
    assert writes==['C:\\new\\APISwitch-v0.1.15.exe --background']


def test_backend_shutdown_escalates_when_graceful_wait_does_not_finish():
    class Server:
        should_exit = False
        force_exit = False

    class Worker:
        join_timeouts: list[float] = []

        def join(self, timeout: float) -> None:
            self.join_timeouts.append(timeout)

        def is_alive(self) -> bool:
            return len(self.join_timeouts) < 2

    server = Server()
    worker = Worker()

    assert _stop_backend_server(server, worker, graceful_timeout=3, force_timeout=2) is True
    assert server.should_exit is True
    assert server.force_exit is True
    assert worker.join_timeouts == [3, 2]


def test_backend_shutdown_does_not_force_a_completed_graceful_exit():
    class Server:
        should_exit = False
        force_exit = False

    class Worker:
        join_timeouts: list[float] = []

        def join(self, timeout: float) -> None:
            self.join_timeouts.append(timeout)

        def is_alive(self) -> bool:
            return False

    server = Server()
    worker = Worker()

    assert _stop_backend_server(server, worker) is True
    assert server.should_exit is True
    assert server.force_exit is False
    assert worker.join_timeouts == [3]


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


def test_port_change_upgrades_legacy_harness_with_independent_key_and_all_callable_models(client, tmp_path):
    provider = client.post(
        "/api/admin/provider-instances",
        json={"name": "legacy-agent", "template_key": "openai", "base_url": "mock://legacy-agent"},
    ).json()
    upstream = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "legacy-upstream"},
    ).json()
    models = []
    for name in ("legacy-main", "legacy-secondary"):
        model = client.post(
            "/api/admin/unified-models",
            json={"name": name, "enabled_protocols": ["openai_chat"]},
        ).json()
        assert client.post(
            f"/api/admin/unified-models/{model['id']}/candidates",
            json={"upstream_model_id": upstream["id"]},
        ).status_code == 201
        models.append(model)

    target = tmp_path / "legacy-dsh.yaml"
    target.write_text(
        "llm-pi-ai:\n  providers:\n    apiswitch:\n      apiKeyEnv: APISWITCH_API_KEY\n",
        encoding="utf-8",
    )
    with SessionLocal() as db:
        db.add(AgentConfig(
            agent_type="deepseek-harness",
            config_path=str(target),
            enabled=True,
            main_model_id=models[0]["id"],
            last_written_base_url="http://127.0.0.1:8080",
        ))
        db.commit()

    assert _refresh_agents_for_port_change(
        "http://127.0.0.1:8080", "http://127.0.0.1:53421"
    ) == 1
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    harness = document["llm-pi-ai"]["providers"]["apiswitch"]
    assert "apiKeyEnv" not in harness
    assert harness["headers"]["Authorization"].startswith("Bearer ask_")
    assert "ask_agent_key_created_when_written" not in harness["headers"]["Authorization"]
    assert {item["id"] for item in harness["models"]} == {item["name"] for item in models}

    saved = client.get("/api/admin/agents").json()[0]
    assert saved["api_token_id"] is not None
    assert set(saved["model_ids"]) == {item["id"] for item in models}
    tokens = client.get("/api/admin/tokens").json()
    assert len(tokens) == 1
    assert set(tokens[0]["unified_model_ids"]) == {item["id"] for item in models}


def test_claude_config_maps_four_unified_models_and_restore_is_atomic(client,tmp_path,monkeypatch):
    models=[]
    for name in ("main","opus","sonnet","haiku"):
        models.append(client.post("/api/admin/unified-models",json={"name":f"agent-{name}","enabled_protocols":["anthropic_messages"]}).json())
    target=tmp_path/"settings.json";target.write_text('{"original":true}',encoding="utf-8")
    monkeypatch.setattr("apiswitch.desktop.runtime_info",lambda:{"base_url":"http://127.0.0.1:8080"})
    payload={"config_path":str(target),"main_model_id":models[0]["id"],"opus_model_id":models[1]["id"],"sonnet_model_id":models[2]["id"],"haiku_model_id":models[3]["id"]}
    preview=client.post("/api/admin/agents/claude-code/preview",json=payload).json()
    preview_content=json.loads(preview["content"])
    assert preview_content["model"]=="agent-main"
    assert preview_content["env"]=={
        "ANTHROPIC_BASE_URL":"http://127.0.0.1:8080",
        "ANTHROPIC_MODEL":"agent-main",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY":"1",
        "ANTHROPIC_AUTH_TOKEN":"ask_agent_key_created_when_written",
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


def test_agent_adapters_preview_merge_backup_and_write(client, tmp_path, monkeypatch):
    provider = client.post(
        "/api/admin/provider-instances",
        json={"name": "agent-vision", "template_key": "openai", "base_url": "mock://agent-vision"},
    ).json()
    main = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "agent-text", "input_capabilities_json": ["text"], "output_capabilities_json": ["text", "tools"]},
    ).json()
    helper = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "agent-vision-helper", "input_capabilities_json": ["text", "vision"], "output_capabilities_json": ["text"]},
    ).json()
    model = client.post(
        "/api/admin/unified-models",
        json={"name": "agent-all", "enabled_protocols": ["openai_chat", "openai_responses", "gemini_v1beta"]},
    ).json()
    assert client.post(f"/api/admin/unified-models/{model['id']}/candidates", json={"upstream_model_id": main["id"]}).status_code == 201
    second_model = client.post(
        "/api/admin/unified-models",
        json={"name": "agent-second", "enabled_protocols": ["openai_chat", "openai_responses", "gemini_v1beta"]},
    ).json()
    assert client.post(f"/api/admin/unified-models/{second_model['id']}/candidates", json={"upstream_model_id": main["id"]}).status_code == 201
    assert client.post("/api/admin/auxiliary/models", json={"upstream_model_id": helper["id"], "capabilities": ["vision"]}).status_code == 201
    assert client.post("/api/admin/auxiliary/workflows", json={"workflow_type": "vision_to_text", "input_capability": "vision", "output_capability": "text"}).status_code == 201
    monkeypatch.setattr("apiswitch.desktop.runtime_info", lambda: {"base_url": "http://127.0.0.1:8080"})
    targets = {
        "codex": tmp_path / "config.toml",
        "opencode": tmp_path / "opencode.json",
        "openclaw": tmp_path / "openclaw.json",
        "deepseek-harness": tmp_path / "dsh-settings.yaml",
        "hermes": tmp_path / "config.yaml",
        "gemini-cli": tmp_path / ".env",
    }
    initial = {
        "codex": 'personality = "friendly"\n',
        "opencode": '{"autoupdate":false}',
        "openclaw": '{"gateway":{"port":18789}}',
        "deepseek-harness": (
            "locale:\n  preference: zh\n"
            "llm-pi-ai:\n  providers:\n    apiswitch:\n      models:\n"
            "        - id: agent-all\n          contextWindow: 12345\n          customFlag: keep-me\n"
        ),
        "hermes": "terminal:\n  backend: local\n",
        "gemini-cli": "KEEP_ME=yes\n",
    }
    for agent_type, target in targets.items():
        target.write_text(initial[agent_type], encoding="utf-8")
        payload = {"config_path": str(target), "main_model_id": model["id"], "model_ids": [model["id"], second_model["id"]]}
        preview = client.post(f"/api/admin/agents/{agent_type}/preview", json=payload)
        assert preview.status_code == 200, preview.text
        assert "ask_agent_key_created_when_written" in preview.json()["content"]
        written = client.post(f"/api/admin/agents/{agent_type}/write", json=payload)
        assert written.status_code == 200, written.text
        assert written.json()["api_token_created"] is True
        assert Path(written.json()["backup_path"]).read_text(encoding="utf-8") == initial[agent_type]

    codex = tomlkit.parse(targets["codex"].read_text(encoding="utf-8"))
    assert codex["personality"] == "friendly" and codex["model"] == "agent-all"
    assert codex["model_providers"]["apiswitch"]["base_url"] == "http://127.0.0.1:8080/v1"
    opencode = json.loads(targets["opencode"].read_text(encoding="utf-8"))
    assert opencode["autoupdate"] is False and opencode["model"] == "apiswitch/agent-all"
    assert opencode["provider"]["apiswitch"]["options"]["apiKey"].startswith("ask_")
    opencode_model = opencode["provider"]["apiswitch"]["models"]["agent-all"]
    assert opencode_model["attachment"] is True
    assert opencode_model["tool_call"] is True
    assert opencode_model["modalities"] == {"input": ["text", "image"], "output": ["text"]}
    assert set(opencode["provider"]["apiswitch"]["models"]) == {"agent-all", "agent-second"}
    openclaw = json.loads(targets["openclaw"].read_text(encoding="utf-8"))
    assert openclaw["gateway"]["port"] == 18789
    assert openclaw["agents"]["defaults"]["model"]["primary"] == "apiswitch/agent-all"
    assert openclaw["models"]["providers"]["apiswitch"]["models"][-1]["input"] == ["text", "image"]
    harness = yaml.safe_load(targets["deepseek-harness"].read_text(encoding="utf-8"))
    assert harness["locale"]["preference"] == "zh"
    harness_provider = harness["llm-pi-ai"]["providers"]["apiswitch"]
    assert harness_provider["baseURL"] == "http://127.0.0.1:8080/v1"
    assert harness_provider["headers"]["Authorization"].startswith("Bearer ask_")
    assert "apiKeyEnv" not in harness_provider
    harness_models = {item["id"]: item for item in harness_provider["models"]}
    assert set(harness_models) == {"agent-all", "agent-second"}
    assert harness_provider["defaultInput"] == ["text", "image"]
    assert all(item["input"] == ["text", "image"] for item in harness_models.values())
    assert harness_models["agent-all"]["contextWindow"] == 12345
    assert harness_models["agent-all"]["customFlag"] == "keep-me"
    assert harness["agent-default-model"] == {"provider": "apiswitch", "model": "agent-all"}
    hermes = yaml.safe_load(targets["hermes"].read_text(encoding="utf-8"))
    assert hermes["terminal"]["backend"] == "local" and hermes["model"]["provider"] == "custom"
    gemini = targets["gemini-cli"].read_text(encoding="utf-8")
    assert "KEEP_ME=yes" in gemini and "GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:8080" in gemini
    assert "GEMINI_MODEL=agent-all" in gemini and "GEMINI_API_KEY=ask_" in gemini

    saved_agents=client.get("/api/admin/agents").json()
    assert len({item["api_token_id"] for item in saved_agents})==6
    assert all(item["model_ids"]==[model["id"],second_model["id"]] for item in saved_agents)
    token_rows=client.get("/api/admin/tokens").json()
    assert len(token_rows)==6
    assert all(set(item["unified_model_ids"])=={model["id"],second_model["id"]} for item in token_rows)

    assert _refresh_agents_for_port_change("http://127.0.0.1:8080", "http://127.0.0.1:53421") == 6
    assert "http://127.0.0.1:53421" in targets["gemini-cli"].read_text(encoding="utf-8")
    assert "http://127.0.0.1:53421/v1" in targets["codex"].read_text(encoding="utf-8")


def test_agent_config_content_is_editable_and_key_rotation_keeps_one_bound_token(client,tmp_path,monkeypatch):
    model=client.post(
        "/api/admin/unified-models",
        json={"name":"editable-agent","enabled_protocols":["openai_chat"]},
    ).json()
    target=tmp_path/"opencode.json"
    monkeypatch.setattr("apiswitch.desktop.runtime_info",lambda:{"base_url":"http://127.0.0.1:8080"})
    payload={"config_path":str(target),"main_model_id":model["id"],"model_ids":[model["id"]]}

    preview=client.post("/api/admin/agents/opencode/preview",json=payload).json()
    editable=json.loads(preview["content"])
    editable["userEdited"]={"keep":True}
    first=client.post(
        "/api/admin/agents/opencode/write",
        json={**payload,"content":json.dumps(editable,ensure_ascii=False)},
    )
    assert first.status_code==200,first.text
    first_prefix=first.json()["api_token_prefix"]
    written=json.loads(target.read_text(encoding="utf-8"))
    first_plain=written["provider"]["apiswitch"]["options"]["apiKey"]
    assert first_plain.startswith("ask_") and written["userEdited"]=={"keep":True}

    existing=client.post("/api/admin/agents/opencode/preview",json=payload).json()
    assert first_plain in existing["content"]
    unchanged=client.post("/api/admin/agents/opencode/write",json={**payload,"content":existing["content"]})
    assert unchanged.status_code==200 and unchanged.json()["api_token_prefix"]==first_prefix
    assert len(client.get("/api/admin/tokens").json())==1

    rotated_preview=client.post("/api/admin/agents/opencode/preview",json={**payload,"rotate_api_key":True}).json()
    assert "ask_agent_key_created_when_written" in rotated_preview["content"]
    rotated=client.post(
        "/api/admin/agents/opencode/write",
        json={**payload,"rotate_api_key":True,"content":rotated_preview["content"]},
    )
    assert rotated.status_code==200,rotated.text
    assert rotated.json()["api_token_prefix"]!=first_prefix
    rotated_plain=json.loads(target.read_text(encoding="utf-8"))["provider"]["apiswitch"]["options"]["apiKey"]
    assert rotated_plain.startswith("ask_") and rotated_plain!=first_plain
    assert len(client.get("/api/admin/tokens").json())==1

    before=target.read_text(encoding="utf-8")
    malformed=client.post("/api/admin/agents/opencode/write",json={**payload,"content":"{"})
    assert malformed.status_code==422 and target.read_text(encoding="utf-8")==before


def test_agent_can_select_an_existing_api_key_without_changing_its_model_permissions(client,tmp_path,monkeypatch):
    models=[]
    for name in ("manual-agent-main","manual-agent-shared"):
        models.append(client.post(
            "/api/admin/unified-models",
            json={"name":name,"enabled_protocols":["openai_chat"]},
        ).json())
    existing=client.post(
        "/api/admin/tokens",
        json={
            "name":"手动选择的客户端 Key",
            "scopes":["gateway:invoke"],
            "unified_model_ids":[item["id"] for item in models],
        },
    ).json()
    target=tmp_path/"manual-opencode.json"
    monkeypatch.setattr("apiswitch.desktop.runtime_info",lambda:{"base_url":"http://127.0.0.1:8080"})
    payload={
        "config_path":str(target),
        "main_model_id":models[0]["id"],
        "model_ids":[models[0]["id"]],
        "api_token_mode":"manual",
        "api_token_id":existing["id"],
        "api_token":existing["token"],
    }

    preview=client.post("/api/admin/agents/opencode/preview",json=payload)
    assert preview.status_code==200,preview.text
    assert existing["token"] in preview.json()["content"]
    written=client.post(
        "/api/admin/agents/opencode/write",
        json={**payload,"content":preview.json()["content"]},
    )
    assert written.status_code==200,written.text
    assert written.json()["api_token_mode"]=="manual"
    assert written.json()["api_token_id"]==existing["id"]
    assert written.json()["api_token_created"] is False

    saved=client.get("/api/admin/agents").json()[0]
    assert saved["api_token_mode"]=="manual"
    assert saved["api_token_id"]==existing["id"]
    assert saved["api_token_name"]=="手动选择的客户端 Key"
    tokens=client.get("/api/admin/tokens").json()
    assert len(tokens)==1
    assert set(tokens[0]["unified_model_ids"])=={item["id"] for item in models}

    # Once bound, the plaintext is preserved from the target config and does
    # not need to be pasted again. A supplied wrong plaintext is still rejected.
    without_plain={key:value for key,value in payload.items() if key!="api_token"}
    assert client.post("/api/admin/agents/opencode/preview",json=without_plain).status_code==200
    wrong=client.post("/api/admin/agents/opencode/preview",json={**payload,"api_token":"ask_wrong_manual_key"})
    assert wrong.status_code==422
    assert "不匹配" in wrong.text

    # Switching back to automatic mode creates a new independent token and
    # leaves the manually selected shared token untouched.
    automatic={
        "config_path":str(target),
        "main_model_id":models[0]["id"],
        "model_ids":[models[0]["id"]],
        "api_token_mode":"auto",
    }
    auto_preview=client.post("/api/admin/agents/opencode/preview",json=automatic).json()
    auto_write=client.post(
        "/api/admin/agents/opencode/write",
        json={**automatic,"content":auto_preview["content"]},
    )
    assert auto_write.status_code==200,auto_write.text
    assert auto_write.json()["api_token_mode"]=="auto"
    assert auto_write.json()["api_token_id"]!=existing["id"]
    assert len(client.get("/api/admin/tokens").json())==2


def test_deleting_agent_config_revokes_only_its_independent_token_and_preserves_files(client,tmp_path,monkeypatch):
    model=client.post(
        "/api/admin/unified-models",
        json={"name":"deletable-agent","enabled_protocols":["openai_chat"]},
    ).json()
    monkeypatch.setattr("apiswitch.desktop.runtime_info",lambda:{"base_url":"http://127.0.0.1:8080"})
    automatic_target=tmp_path/"automatic-opencode.json"
    automatic_payload={"config_path":str(automatic_target),"main_model_id":model["id"],"model_ids":[model["id"]]}
    automatic_preview=client.post("/api/admin/agents/opencode/preview",json=automatic_payload).json()
    automatic_write=client.post(
        "/api/admin/agents/opencode/write",
        json={**automatic_payload,"content":automatic_preview["content"]},
    )
    assert automatic_write.status_code==200,automatic_write.text
    independent_token_id=automatic_write.json()["api_token_id"]

    deleted=client.delete("/api/admin/agents/opencode")
    assert deleted.status_code==200,deleted.text
    assert deleted.json()=={
        "deleted":True,
        "agent_type":"opencode",
        "api_token_deleted":True,
        "config_file_preserved":True,
        "config_path":str(automatic_target),
    }
    assert automatic_target.is_file()
    assert client.get("/api/admin/agents").json()==[]
    assert all(row["id"]!=independent_token_id for row in client.get("/api/admin/tokens").json())

    shared=client.post(
        "/api/admin/tokens",
        json={"name":"shared-agent-key","scopes":["gateway:invoke"],"unified_model_ids":[model["id"]]},
    ).json()
    manual_target=tmp_path/"manual-opencode.json"
    manual_payload={
        "config_path":str(manual_target),"main_model_id":model["id"],"model_ids":[model["id"]],
        "api_token_mode":"manual","api_token_id":shared["id"],"api_token":shared["token"],
    }
    manual_preview=client.post("/api/admin/agents/opencode/preview",json=manual_payload).json()
    manual_write=client.post(
        "/api/admin/agents/opencode/write",
        json={**manual_payload,"content":manual_preview["content"]},
    )
    assert manual_write.status_code==200,manual_write.text

    deleted_manual=client.delete("/api/admin/agents/opencode")
    assert deleted_manual.status_code==200,deleted_manual.text
    assert deleted_manual.json()["api_token_deleted"] is False
    assert manual_target.is_file()
    assert any(row["id"]==shared["id"] for row in client.get("/api/admin/tokens").json())
    assert client.delete("/api/admin/agents/opencode").status_code==404


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

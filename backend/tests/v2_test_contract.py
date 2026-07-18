"""Generation-2 contract smoke tests; historical Connection/Node tests are retired."""
from uuid import uuid4

from fastapi.testclient import TestClient


def _provider(client: TestClient) -> int:
    response = client.post("/api/admin/provider-instances", json={"name": f"mock-{uuid4().hex}", "template_key": "openai", "base_url": "mock://unit", "api_key": "unit-only-not-a-real-key"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_generation_two_provider_model_route_and_protocols(client: TestClient):
    assert client.get("/api/admin/provider-templates").status_code == 200
    provider_id = _provider(client)
    created = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models", json={"model_id": "mock-text", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]})
    assert created.status_code == 201
    upstream_id = created.json()["id"]
    unified = client.post("/api/admin/unified-models", json={"name": "stable-model", "enabled_protocols": ["openai_chat", "openai_responses", "anthropic_messages", "gemini_v1beta"], "routing_mode": "combo", "combo_strategy": "priority"}).json()
    candidate = client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_id, "priority": 1, "weight": 100})
    assert candidate.status_code == 201
    token = client.post("/api/admin/tokens", json={"name": "contract", "scopes": ["gateway:invoke"], "unified_model_ids": [unified["id"]]}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/v1/chat/completions", headers=headers, json={"model": "stable-model", "messages": [{"role":"user","content":"hello"}]}).status_code == 200
    assert client.post("/v1/responses", headers=headers, json={"model": "stable-model", "input": "hello"}).status_code == 200
    assert client.post("/v1/messages", headers={"x-api-key":token,"anthropic-version":"2023-06-01"}, json={"model": "stable-model", "max_tokens": 8, "messages": [{"role":"user","content":"hello"}]}).status_code == 200
    duplicated_prefix=client.post("/v1/v1/messages",headers={"x-api-key":token,"anthropic-version":"2023-06-01"},json={"model":"stable-model","max_tokens":8,"messages":[{"role":"user","content":"hello"}]})
    assert duplicated_prefix.status_code==200,duplicated_prefix.text
    assert duplicated_prefix.json()["model"]=="stable-model"
    assert client.post("/v1beta/models/stable-model:generateContent", headers={"x-goog-api-key":token}, json={"contents": [{"parts": [{"text":"hello"}]}]}).status_code == 200
    gemini_models=client.get("/v1beta/models",params={"key":token,"pageSize":1000})
    assert gemini_models.status_code==200,gemini_models.text
    assert gemini_models.json()=={"models":[{"name":"models/stable-model","baseModelId":"stable-model","version":"1","displayName":"stable-model","description":"APISwitch unified model","supportedGenerationMethods":["generateContent"]}]}
    gemini_model=client.get("/v1beta/models/stable-model",headers={"x-goog-api-key":token})
    assert gemini_model.status_code==200
    assert gemini_model.json()["name"]=="models/stable-model"


def test_auxiliary_modes_and_remote_missing_reference(client: TestClient):
    provider_id = _provider(client)
    upstream_id = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models", json={"model_id":"vision","input_capabilities_json":["vision"],"output_capabilities_json":["text"]}).json()["id"]
    unified_id = client.post("/api/admin/unified-models", json={"name":"vision-stable","enabled_protocols":["openai_chat"]}).json()["id"]
    assert client.patch("/api/admin/auxiliary/settings",json={"mode":"global_pool"}).json()["mode"] == "global_pool"
    assert client.post("/api/admin/auxiliary/models",json={"upstream_model_id":upstream_id,"capabilities":["vision"]}).status_code == 201
    assert client.post("/api/admin/auxiliary/workflows",json={"workflow_type":"vision_to_text","input_capability":"vision","output_capability":"text","ordered_steps":[{"input":"vision","output":"text"}]}).status_code == 201
    sync=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models/sync",json={"models":[]})
    assert sync.status_code == 200 and sync.json()["marked_missing"] == 1


def test_all_documented_gateway_entrypoints_use_the_token_protected_pipeline(client: TestClient):
    provider_id = _provider(client)
    capabilities = ["text", "embeddings", "images", "audio", "moderation", "rerank", "search", "video", "music"]
    upstream = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models", json={"model_id": "mock-all", "input_capabilities_json": capabilities, "output_capabilities_json": capabilities}).json()
    protocols = ["openai_chat", "openai_responses", "anthropic_messages", "gemini_v1beta", "embeddings", "images", "audio", "moderations", "rerank", "search", "batches", "websocket", "video", "music"]
    unified = client.post("/api/admin/unified-models", json={"name": "all-capabilities", "enabled_protocols": protocols}).json()
    assert client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream["id"]}).status_code == 201
    token = client.post("/api/admin/tokens", json={"name": "all-protocols", "unified_model_ids": [unified["id"]]}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    for endpoint, payload in [
        ("/v1/embeddings", {"model": "all-capabilities", "input": "x"}),
        ("/v1/images/generations", {"model": "all-capabilities", "prompt": "x"}),
        ("/v1/images/edits", {"model": "all-capabilities", "prompt": "x"}),
        ("/v1/images/variations", {"model": "all-capabilities", "image": "x"}),
        ("/v1/audio/speech", {"model": "all-capabilities", "input": "x"}),
        ("/v1/audio/transcriptions", {"model": "all-capabilities", "file": "x"}),
        ("/v1/moderations", {"model": "all-capabilities", "input": "x"}),
        ("/v1/rerank", {"model": "all-capabilities", "query": "x"}),
        ("/v1/search", {"model": "all-capabilities", "query": "x"}),
    ]:
        assert client.post(endpoint, headers=headers, json=payload).status_code == 200, endpoint
    batch_jsonl=b'{"custom_id":"one","method":"POST","url":"/v1/chat/completions","body":{"model":"all-capabilities","messages":[{"role":"user","content":"batch"}]}}\n'
    batch_input=client.post("/v1/files",headers=headers,files={"file":("batch.jsonl",batch_jsonl,"application/jsonl")}).json()
    batch=client.post("/v1/batches",headers=headers,json={"input_file_id":batch_input["id"],"endpoint":"/v1/chat/completions"})
    assert batch.status_code==200 and batch.json()["request_counts"]=={"total":1,"completed":1,"failed":0}
    assert client.get(f"/v1/batches/{batch.json()['id']}",headers=headers).json()["output_file_id"]
    assert client.get(f"/v1/files/{batch.json()['output_file_id']}",headers=headers).status_code==200
    video=client.post("/v1/videos/generations",headers=headers,json={"model":"all-capabilities","prompt":"x"})
    music=client.post("/v1/music/generations",headers=headers,json={"model":"all-capabilities","prompt":"x"})
    assert video.status_code==music.status_code==200
    assert client.get(f"/v1/videos/{video.json()['id']}",headers=headers).json()["status"]=="completed"
    assert client.get(f"/v1/music/{music.json()['id']}",headers=headers).json()["status"]=="completed"
    created = client.post("/v1/files", headers=headers, files={"file": ("sample.txt", b"mock-content", "text/plain")})
    assert created.status_code == 200
    assert client.get(f"/v1/files/{created.json()['id']}", headers=headers).status_code == 200
    with client.websocket_connect("/v1/ws/chat/completions", headers=headers) as socket:
        socket.send_json({"model": "all-capabilities", "messages": [{"role": "user", "content": "x"}]})
        assert socket.receive_json()["event"] == "start"
        assert socket.receive_json()["event"] == "content_delta"
        assert socket.receive_json()["event"] == "completed"
    status = client.get("/api/admin/router/status").json()
    matrix = {item["protocol"]: item for item in status["matrix"][str(unified["id"])]}
    assert matrix["openai_chat"]["status"] == "native"
    assert matrix["anthropic_messages"]["status"] == "lossless"
    assert matrix["images"]["status"] == "lossless"
    assert status["health"]


def test_agent_webdav_settings_and_structured_dry_run(client: TestClient, monkeypatch):
    assert client.patch("/api/admin/settings", json={"preferred_port": 8123, "upload_limit_bytes": 1234}).status_code == 200
    main_model = client.post(
        "/api/admin/unified-models",
        json={"name": "claude-contract-main", "enabled_protocols": ["anthropic_messages"]},
    ).json()
    preview = client.post(
        "/api/admin/agents/claude-code/preview",
        json={"main_model_id": main_model["id"]},
    )
    assert preview.status_code == 200 and preview.json()["base_url"].startswith("http://127.0.0.1:")
    profile = client.post("/api/admin/webdav/profiles", json={"name": "mock-dav", "url": "https://dav.invalid/root", "username": "unit", "password": "not-a-real-secret", "backup_password": "separate-unit-password"})
    assert profile.status_code == 201
    monkeypatch.setattr("apiswitch.backup.webdav.test", lambda *args: None)
    assert client.post(f"/api/admin/webdav/profiles/{profile.json()['id']}/test").json()["mode"] == "remote"
    dry = client.post("/api/admin/router/convert/test", json={"protocol": "openai_chat", "request": {"model": "missing", "messages": []}})
    assert dry.status_code == 200 and dry.json()["error"]["stage"] == "model_lookup"


def test_budget_crud_startup_status_and_restore_confirmation(client: TestClient):
    created = client.post("/api/admin/budgets", json={"name": "monthly", "scope": "global", "monthly_limit": 25, "enforcement_action": "reject"})
    assert created.status_code == 201
    budget_id = created.json()["id"]
    assert client.patch(f"/api/admin/budgets/{budget_id}", json={"enabled": False, "monthly_limit": 30}).status_code == 200
    budget = next(item for item in client.get("/api/admin/budgets").json() if item["id"] == budget_id)
    assert budget["enabled"] is False and budget["monthly_limit"] == 30
    assert client.delete(f"/api/admin/budgets/{budget_id}").json() == {"deleted": True}
    assert client.get("/api/admin/settings/startup").status_code == 200
    refused = client.post("/api/admin/database/restore", json={"archive_path": "missing.apsbak", "backup_password": "unit-password"})
    assert refused.status_code == 422
    assert refused.json()["detail"]["type"] == "confirmation_required"


def test_unified_model_reference_guard_and_system_setting_validation(client: TestClient):
    provider_id = _provider(client)
    upstream = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={"model_id": "aux-reference", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": "referenced-unified", "enabled_protocols": ["openai_chat"]},
    ).json()
    auxiliary = client.post(
        "/api/admin/auxiliary/models",
        json={"upstream_model_id": upstream["id"], "unified_model_id": unified["id"], "capabilities": ["text"]},
    )
    assert auxiliary.status_code == 201
    blocked = client.delete(f"/api/admin/unified-models/{unified['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["details"]["auxiliary_models"] == 1
    assert client.patch("/api/admin/settings", json={"preferred_port": 0}).status_code == 422
    assert client.patch("/api/admin/settings", json={"upload_limit_bytes": -1}).status_code == 422


def test_gateway_switch_blocks_protocols_but_keeps_admin_available(client: TestClient, gateway_headers: dict[str, str]):
    initial = client.get("/api/admin/settings")
    assert initial.status_code == 200
    assert initial.json()["gateway_enabled"] is True

    disabled = client.patch("/api/admin/settings", json={"gateway_enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["gateway_enabled"] is False

    blocked = client.get("/v1/models", headers=gateway_headers)
    assert blocked.status_code == 503
    assert blocked.json()["detail"] == {
        "type": "gateway_disabled",
        "message": "网关已在系统设置中停用",
        "stage": "gateway_switch",
    }
    assert client.get("/api/admin/runtime").status_code == 200

    with client.websocket_connect("/v1/ws/chat/completions", headers=gateway_headers) as websocket:
        assert websocket.receive_json()["error"]["type"] == "gateway_disabled"

    invalid = client.patch("/api/admin/settings", json={"gateway_enabled": "false"})
    assert invalid.status_code == 422
    enabled = client.patch("/api/admin/settings", json={"gateway_enabled": True})
    assert enabled.status_code == 200
    assert client.get("/v1/models", headers=gateway_headers).status_code == 200


def test_dashboard_summary_is_available_in_generation_two_admin_api(client: TestClient):
    response = client.get("/api/admin/dashboard/summary")
    assert response.status_code == 200
    assert response.json() == {
        "requests_total": 0,
        "success_rate": 1.0,
        "failure_rate": 0.0,
        "average_latency_ms": 0.0,
        "first_token_latency_ms": 0,
        "open_circuit_breakers": 0,
        "monthly_budget_used": 0.0,
        "monthly_budget_limit": 0.0,
        "recent_errors": [],
        "provider_instances":0,
        "available_upstream_models":0,
        "unified_models":0,
        "auxiliary_models":0,
        "requests_24h":0,
        "cost_24h":0.0,
        "budget_alerts":0,
    }

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _base_route(client: TestClient):
    provider = client.post("/api/admin/provider-instances", json={"name": f"aux-{uuid4().hex}", "template_key": "openai", "base_url": "mock://auxiliary"}).json()
    main = client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models", json={"model_id": "main-text", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]}).json()
    capabilities = ["text", "vision", "files", "long_context", "tools", "tool_results", "audio", "json", "embeddings", "images", "video", "music"]
    auxiliary = client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models", json={"model_id": "aux-all", "input_capabilities_json": capabilities, "output_capabilities_json": capabilities}).json()
    unified = client.post("/api/admin/unified-models", json={"name": f"assisted-{uuid4().hex}", "enabled_protocols": ["openai_chat", "embeddings"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": main["id"]})
    token = client.post("/api/admin/tokens", json={"name": "aux-client", "unified_model_ids": [unified["id"]]}).json()["token"]
    return auxiliary, unified, {"Authorization": f"Bearer {token}"}


def _vision_request(model: str) -> dict:
    return {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": "describe"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]}]}


def test_configured_auxiliary_workflow_executes_before_main_candidate(client: TestClient):
    auxiliary, unified, headers = _base_route(client)
    client.post("/api/admin/auxiliary/models", json={"upstream_model_id": auxiliary["id"], "capabilities": ["vision"], "priority": 1})
    client.post("/api/admin/auxiliary/workflows", json={"workflow_type": "vision_to_text", "input_capability": "vision", "output_capability": "text", "ordered_steps": [{"input": "vision", "output": "text"}]})

    response = client.post("/v1/chat/completions", headers=headers, json=_vision_request(unified["name"]))

    assert response.status_code == 200, response.text
    log = client.get("/api/admin/logs").json()[0]
    assert log["success"] is True
    assert log["auxiliary_summary"]["mode"] == "global_pool"
    assert log["auxiliary_summary"]["steps"][0]["status"] == "succeeded"
    assert log["auxiliary_summary"]["steps"][0]["upstream_model_id"] == auxiliary["id"]


def test_auxiliary_workflow_without_configured_model_fails_before_main_call(client: TestClient):
    _, unified, headers = _base_route(client)
    client.post("/api/admin/auxiliary/workflows", json={"workflow_type": "vision_to_text", "input_capability": "vision", "output_capability": "text", "ordered_steps": [{"input": "vision", "output": "text"}]})

    response = client.post("/v1/chat/completions", headers=headers, json=_vision_request(unified["name"]))

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "auxiliary_workflow_not_configured"
    log = client.get("/api/admin/logs").json()[0]
    assert log["success"] is False and log["failure_stage"] == "auxiliary_plan"


def test_all_documented_auxiliary_workflows_execute_and_log_ordered_steps(client: TestClient):
    cases = [
        ("file_extract", "files", "text", "/v1/chat/completions", lambda model: {"model": model, "messages": [{"role": "user", "content": [{"type": "input_file", "file_id": "file_mock"}]}]}),
        ("context_compress", "long_context", "text", "/v1/chat/completions", lambda model: {"model": model, "messages": [{"role": "user", "content": "x" * 32001}]}),
        ("tool_plan", "tools", "tool_results", "/v1/chat/completions", lambda model: {"model": model, "messages": [{"role": "user", "content": "plan"}], "tools": [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]}),
        ("audio_transcribe", "audio", "text", "/v1/chat/completions", lambda model: {"model": model, "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "AA==", "format": "wav"}}]}]}),
        ("structured_repair", "json", "json", "/v1/chat/completions", lambda model: {"model": model, "messages": [{"role": "user", "content": "json"}], "response_format": {"type": "json_object"}}),
        ("terminal_capability", "embeddings", "embeddings", "/v1/embeddings", lambda model: {"model": model, "input": "embed"}),
    ]
    for workflow_type,input_capability,output_capability,endpoint,payload_factory in cases:
        auxiliary, unified, headers = _base_route(client)
        assert client.post("/api/admin/auxiliary/models", json={"upstream_model_id": auxiliary["id"], "capabilities": [input_capability], "priority": 1}).status_code == 201
        assert client.post("/api/admin/auxiliary/workflows", json={"workflow_type": workflow_type, "input_capability": input_capability, "output_capability": output_capability, "ordered_steps": [{"input": input_capability, "output": output_capability, "timeout_seconds": 3}]}).status_code == 201
        response = client.post(endpoint, headers=headers, json=payload_factory(unified["name"]))
        assert response.status_code == 200, (workflow_type, response.text)
        step = client.get("/api/admin/logs").json()[0]["auxiliary_summary"]["steps"][0]
        assert step["workflow_type"] == workflow_type
        assert step["status"] == "succeeded"
        assert step["timeout_seconds"] == 3

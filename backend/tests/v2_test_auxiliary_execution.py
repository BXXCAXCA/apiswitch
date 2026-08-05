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
    logs = client.get("/api/admin/logs").json()
    log = next(item for item in logs if item["request_kind"] == "main")
    auxiliary_log = next(item for item in logs if item["request_kind"] == "auxiliary")
    assert log["success"] is True
    assert log["auxiliary_summary"]["mode"] == "global_pool"
    assert log["auxiliary_summary"]["steps"][0]["status"] == "succeeded"
    assert log["auxiliary_summary"]["steps"][0]["upstream_model_id"] == auxiliary["id"]
    assert auxiliary_log["parent_request_id"] == log["request_id"]
    assert auxiliary_log["provider_instance_id"] is not None
    assert auxiliary_log["upstream_model_id"] == auxiliary["id"]
    assert auxiliary_log["inbound_protocol"] == "auxiliary"
    assert client.get("/api/admin/logs", params={"request_kind": "auxiliary"}).json() == [auxiliary_log]


def test_vision_to_text_replaces_images_before_text_only_main_model(client: TestClient, monkeypatch):
    auxiliary, unified, headers = _base_route(client)
    client.post("/api/admin/auxiliary/models", json={"upstream_model_id": auxiliary["id"], "capabilities": ["vision"], "priority": 1})
    client.post("/api/admin/auxiliary/workflows", json={"workflow_type": "vision_to_text", "input_capability": "vision", "output_capability": "text", "ordered_steps": [{"input": "vision", "output": "text"}]})

    captured: list[dict] = []
    from apiswitch.routing import executor
    original = executor._call_http

    async def capture(candidate, request):
        captured.append({"model": candidate.upstream.model_id, "messages": request.messages})
        return await original(candidate, request)

    monkeypatch.setattr(executor, "_call_http", capture)
    response = client.post("/v1/chat/completions", headers=headers, json=_vision_request(unified["name"]))

    assert response.status_code == 200, response.text
    main_request = next(item for item in captured if item["model"] == "main-text")
    content = main_request["messages"][0]["content"]
    assert isinstance(content, str)
    assert "APISwitch 图像辅助识别结果" in content
    assert "image_url" not in content


def test_auxiliary_reasoning_wrapper_is_not_injected_into_main_prompt():
    from apiswitch.routing.executor import _clean_auxiliary_text, _replace_vision_content

    description = _clean_auxiliary_text("<think>private reasoning</think>Visible car description")
    messages = _replace_vision_content(_vision_request("model")["messages"], description)
    content = messages[0]["content"]
    assert "private reasoning" not in content
    assert "Visible car description" in content
    assert "APISwitch 图像辅助识别结果" in content
    assert _clean_auxiliary_text("<think>unfinished private reasoning") == ""


def test_auxiliary_workflow_extends_declared_unified_input_capabilities(client: TestClient):
    provider = client.post(
        "/api/admin/provider-instances",
        json={"name": f"aux-declared-{uuid4().hex}", "template_key": "openai", "base_url": "mock://auxiliary"},
    ).json()
    main = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "declared-main-text", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    auxiliary = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "declared-vision-helper", "input_capabilities_json": ["text", "vision"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={
            "name": f"declared-assisted-{uuid4().hex}",
            "enabled_protocols": ["openai_chat"],
            "required_capabilities": {"input": ["vision"], "output": []},
        },
    ).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": main["id"]})
    client.post("/api/admin/auxiliary/models", json={"upstream_model_id": auxiliary["id"], "capabilities": ["vision"]})
    client.post(
        "/api/admin/auxiliary/workflows",
        json={"workflow_type": "vision_to_text", "input_capability": "vision", "output_capability": "text"},
    )
    token = client.post("/api/admin/tokens", json={"name": "declared-aux-client", "unified_model_ids": [unified["id"]]}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    models = client.get("/v1/models", headers=headers).json()["data"]
    advertised = next(item for item in models if item["id"] == unified["name"])
    assert "vision" in advertised["input_capabilities"]
    assert "text" in advertised["input_capabilities"]
    assert "image-recognition" in advertised["capabilities"]
    assert "image-recognition" in advertised["supported_features"]
    assert advertised["input_modalities"] == ["text", "image"]
    assert advertised["inputModalities"] == ["text", "image"]
    assert advertised["supported_input_modalities"] == ["text", "image"]
    assert "image" in advertised["modalities"]["input"]
    assert advertised["architecture"]["input_modalities"] == ["text", "image"]

    response = client.post("/v1/chat/completions", headers=headers, json=_vision_request(unified["name"]))
    assert response.status_code == 200, response.text
    log = client.get("/api/admin/logs").json()[0]
    assert log["auxiliary_summary"]["steps"][0]["status"] == "succeeded"


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

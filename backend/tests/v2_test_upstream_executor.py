from __future__ import annotations

import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from apiswitch.db.models import CircuitBreaker
from apiswitch.db.session import SessionLocal
from apiswitch.routing import executor


def _provider(client: TestClient, base_url: str) -> int:
    response = client.post("/api/admin/provider-instances", json={
        "name": f"simulated-http-{uuid4().hex}", "template_key": "openai", "base_url": base_url,
        "api_key": "unit-placeholder-credential", "custom_headers": {"X-APISwitch-Test": "transport"},
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _token(client: TestClient) -> dict[str, str]:
    model_ids=[item["id"] for item in client.get("/api/admin/unified-models").json()]
    token = client.post("/api/admin/tokens", json={"name": f"transport-{uuid4().hex}","unified_model_ids":model_ids}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_openai_compatible_http_upstream_is_called_and_normalized(client: TestClient, monkeypatch):
    captured = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append((request, payload))
        return httpx.Response(200, json={
            "id": "simulated", "object": "chat.completion", "model": payload["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "simulated upstream reply"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        })

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://upstream.invalid/v1")
    upstream_model = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models", json={"model_id": "remote-chat", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"], "input_price": 1, "output_price": 2}).json()
    unified = client.post("/api/admin/unified-models", json={"name": f"http-{uuid4().hex}", "enabled_protocols": ["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_model["id"], "priority": 1})

    response = client.post("/v1/chat/completions", headers=_token(client), json={"model": unified["name"], "messages": [{"role": "user", "content": "hello"}]})

    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "simulated upstream reply"
    assert response.json()["model"] == unified["name"]
    assert captured[0][0].url.path == "/v1/chat/completions"
    assert captured[0][0].headers["authorization"] == "Bearer unit-placeholder-credential"
    assert captured[0][0].headers["x-apiswitch-test"] == "transport"
    assert captured[0][1]["model"] == "remote-chat"
    log = client.get("/api/admin/logs").json()[0]
    assert log["success"] is True and log["upstream_model_id"] == upstream_model["id"]
    assert log["provider_name"].startswith("simulated-http-")
    assert log["upstream_model_name"] == "remote-chat"
    filtered = client.get("/api/admin/logs", params={
        "provider_instance_id": provider_id, "upstream_model_id": upstream_model["id"],
        "inbound_protocol": "openai_chat", "unified_model": unified["name"],
        "success": "true", "min_cost": 0.00002, "max_cost": 0.00003,
    })
    assert filtered.status_code == 200 and [item["request_id"] for item in filtered.json()] == [log["request_id"]]
    assert client.get("/api/admin/logs", params={"min_cost": 0.1}).json() == []


def test_terminal_protocols_use_their_real_http_paths_and_native_multipart(client: TestClient, monkeypatch):
    captured: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/v1/audio/speech":
            return httpx.Response(200, content=b"mock-audio", headers={"content-type": "audio/mpeg"})
        return httpx.Response(200, json={"data": [{"ok": True}], "text": "ok"})

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://terminal.invalid/v1")
    capabilities = ["text", "embeddings", "images", "audio", "moderation", "rerank", "search", "video", "music"]
    upstream_model = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={
            "model_id": "terminal-all",
            "input_capabilities_json": capabilities,
            "output_capabilities_json": capabilities,
        },
    ).json()
    protocols = ["embeddings", "images", "audio", "moderations", "rerank", "search", "video", "music"]
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": f"terminal-{uuid4().hex}", "enabled_protocols": protocols},
    ).json()
    client.post(
        f"/api/admin/unified-models/{unified['id']}/candidates",
        json={"upstream_model_id": upstream_model["id"]},
    )
    headers = _token(client)

    json_cases = [
        ("/v1/embeddings", "/v1/embeddings", {"input": "hello"}),
        ("/v1/images/generations", "/v1/images/generations", {"prompt": "cat"}),
        ("/v1/audio/speech", "/v1/audio/speech", {"input": "hello", "voice": "alloy"}),
        ("/v1/moderations", "/v1/moderations", {"input": "safe"}),
        ("/v1/rerank", "/v1/rerank", {"query": "q", "documents": ["d"]}),
        ("/v1/search", "/v1/search", {"query": "q"}),
    ]
    for ingress, upstream_path, body in json_cases:
        response = client.post(ingress, headers=headers, json={"model": unified["name"], **body})
        assert response.status_code == 200, (ingress, response.text)
        request = captured[-1]
        assert request.url.path == upstream_path
        forwarded = json.loads(request.content)
        assert forwarded["model"] == "terminal-all"
        assert not any(key.startswith("_apiswitch_") for key in forwarded)
        if ingress == "/v1/audio/speech":
            assert response.content == b"mock-audio"
            assert response.headers["content-type"].startswith("audio/mpeg")
            assert response.headers["x-apiswitch-model"] == unified["name"]

    for ingress, upstream_path in [
        ("/v1/videos/generations", "/v1/videos/generations"),
        ("/v1/music/generations", "/v1/music/generations"),
    ]:
        response = client.post(ingress, headers=headers, json={"model": unified["name"], "prompt": "demo"})
        assert response.status_code == 200, (ingress, response.text)
        assert response.json()["status"] == "completed"
        assert captured[-1].url.path == upstream_path

    multipart_cases = [
        ("/v1/images/edits", "/v1/images/edits", "image", "image.png", b"image-edit"),
        ("/v1/images/variations", "/v1/images/variations", "image", "image.png", b"image-variation"),
        ("/v1/audio/transcriptions", "/v1/audio/transcriptions", "file", "audio.wav", b"audio-bytes"),
    ]
    for ingress, upstream_path, field, filename, content in multipart_cases:
        response = client.post(
            ingress,
            headers=headers,
            data={"model": unified["name"], "prompt": "native multipart"},
            files={field: (filename, content, "application/octet-stream")},
        )
        assert response.status_code == 200, (ingress, response.text)
        request = captured[-1]
        assert request.url.path == upstream_path
        assert request.headers["content-type"].startswith("multipart/form-data;"), [
            (item.url.path, item.headers.get("content-type")) for item in captured[-3:]
        ]
        assert filename.encode() in request.content
        assert content in request.content
        assert b'terminal-all' in request.content


def test_native_anthropic_and_gemini_upstreams_preserve_protocol_parameters(client: TestClient, monkeypatch):
    captured: list[tuple[httpx.Request, dict]] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append((request, payload))
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={
                "id": "msg_native",
                "type": "message",
                "content": [{"type": "text", "text": "anthropic-native"}],
                "usage": {"input_tokens": 2, "output_tokens": 3},
            })
        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": '{"ok":true}'}]}}],
            "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 3},
        })

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))

    anthropic_provider = client.post("/api/admin/provider-instances", json={
        "name": f"native-anthropic-{uuid4().hex}",
        "template_key": "anthropic",
        "base_url": "https://anthropic-native.invalid",
        "api_key": "anthropic-unit-key",
    }).json()
    anthropic_upstream = client.post(
        f"/api/admin/provider-instances/{anthropic_provider['id']}/upstream-models",
        json={"model_id": "claude-native", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    anthropic_model = client.post("/api/admin/unified-models", json={
        "name": f"anthropic-native-{uuid4().hex}", "enabled_protocols": ["anthropic_messages"],
    }).json()
    client.post(f"/api/admin/unified-models/{anthropic_model['id']}/candidates", json={"upstream_model_id": anthropic_upstream["id"]})

    gemini_provider = client.post("/api/admin/provider-instances", json={
        "name": f"native-gemini-{uuid4().hex}",
        "template_key": "gemini",
        "base_url": "https://gemini-native.invalid",
        "api_key": "gemini-unit-key",
    }).json()
    gemini_upstream = client.post(
        f"/api/admin/provider-instances/{gemini_provider['id']}/upstream-models",
        json={"model_id": "gemini-native", "input_capabilities_json": ["text"], "output_capabilities_json": ["text", "json"]},
    ).json()
    gemini_model = client.post("/api/admin/unified-models", json={
        "name": f"gemini-native-{uuid4().hex}", "enabled_protocols": ["gemini_v1beta"],
    }).json()
    client.post(f"/api/admin/unified-models/{gemini_model['id']}/candidates", json={"upstream_model_id": gemini_upstream["id"]})
    token = client.post("/api/admin/tokens", json={
        "name": "native-provider-protocols",
        "unified_model_ids": [anthropic_model["id"], gemini_model["id"]],
    }).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    anthropic = client.post("/v1/messages", headers=headers, json={
        "model": anthropic_model["name"],
        "max_tokens": 64,
        "temperature": 0.2,
        "stop_sequences": ["END"],
        "system": "system",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert anthropic.status_code == 200 and anthropic.json()["content"][0]["text"] == "anthropic-native"
    anthropic_request, anthropic_payload = captured[-1]
    assert anthropic_request.url.path == "/v1/messages"
    assert anthropic_request.headers["x-api-key"] == "anthropic-unit-key"
    assert anthropic_payload["max_tokens"] == 64
    assert anthropic_payload["temperature"] == 0.2
    assert anthropic_payload["stop_sequences"] == ["END"]
    assert anthropic_payload["system"] == "system"

    gemini = client.post(f"/v1beta/models/{gemini_model['name']}:generateContent", headers=headers, json={
        "contents": [{"role": "user", "parts": [{"text": "hello"}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.8,
            "topK": 20,
            "maxOutputTokens": 128,
            "stopSequences": ["STOP"],
            "responseMimeType": "application/json",
            "responseSchema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
    })
    assert gemini.status_code == 200 and gemini.json()["candidates"][0]["content"]["parts"][0]["text"] == '{"ok":true}'
    gemini_request, gemini_payload = captured[-1]
    assert gemini_request.url.path == "/v1beta/models/gemini-native:generateContent"
    assert gemini_request.url.params["key"] == "gemini-unit-key"
    assert gemini_payload["generationConfig"] == {
        "temperature": 0.3,
        "topP": 0.8,
        "topK": 20,
        "maxOutputTokens": 128,
        "stopSequences": ["STOP"],
        "responseMimeType": "application/json",
        "responseSchema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
    }

    unsupported = client.post(f"/v1beta/models/{gemini_model['name']}:generateContent", headers=headers, json={
        "contents": [{"parts": [{"text": "hello"}]}],
        "generationConfig": {"candidateCount": 2},
    })
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["type"] == "protocol_conversion_unsupported"


def test_openai_compatible_legacy_text_choice_is_normalized_for_plain_chat(client: TestClient, monkeypatch):
    def upstream(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "simulated-completion",
            "object": "text_completion",
            "choices": [{"index": 0, "text": "legacy text reply", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        })

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://legacy-text.invalid/v1")
    upstream_model = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={"model_id": "namespace/text-generation", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": f"legacy-text-{uuid4().hex}", "enabled_protocols": ["openai_chat"]},
    ).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_model["id"]})

    response = client.post(
        "/v1/chat/completions",
        headers=_token(client),
        json={"model": unified["name"], "messages": [{"role": "user", "content": "hello"}], "stream": True},
    )
    assert response.status_code == 200, response.text
    assert "legacy text reply" in response.text


def test_completed_json_delta_is_normalized_but_unfinished_delta_is_rejected(client: TestClient, monkeypatch):
    completed=True
    include_object=True

    def upstream(_:httpx.Request)->httpx.Response:
        payload={
            "id":"chunk",
            "choices":[{"index":0,"delta":{"role":"assistant","content":"completed delta reply"},"finish_reason":"stop" if completed else None}],
            "usage":{"completion_tokens":3},
        }
        if include_object:payload["object"]="chat.completion.chunk"
        return httpx.Response(200,json=payload)

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider_id=_provider(client,"https://json-delta.invalid/v1")
    upstream_model=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":"json-delta","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"json-delta-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream_model["id"]})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}],"stream":True}

    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==200 and "completed delta reply" in response.text
    include_object=False
    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==200 and "completed delta reply" in response.text
    completed=False
    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==400
    assert response.json()["error"]["type"]=="invalid_upstream_response"
    breaker=next(row for row in client.get("/api/admin/router/status").json()["circuit_breakers"] if row["upstream_model_id"]==upstream_model["id"])
    assert breaker["state"]=="closed" and breaker["consecutive_failures"]==0


def test_openai_message_text_parts_are_losslessly_joined(client:TestClient,monkeypatch):
    non_text=False

    def upstream(_:httpx.Request)->httpx.Response:
        content=[{"type":"text","text":"hello "},{"type":"output_text","text":"from parts"}]
        if non_text:content.append({"type":"image","image_url":"https://example.invalid/image.png"})
        return httpx.Response(200,json={"object":"chat.completion","choices":[{"message":{"role":"assistant","content":content},"finish_reason":"stop"}],"usage":{}})

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider_id=_provider(client,"https://content-parts.invalid/v1")
    upstream_model=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":"content-parts","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"content-parts-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream_model["id"]})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}

    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==200
    assert response.json()["choices"][0]["message"]["content"]=="hello from parts"
    non_text=True
    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==400
    assert response.json()["error"]["type"]=="invalid_upstream_response"


def test_nullable_tool_arrays_and_reasoning_content_are_preserved(client:TestClient,monkeypatch):
    upstream_requests=[]
    def upstream(request:httpx.Request)->httpx.Response:
        upstream_requests.append(json.loads(request.content))
        message={"role":"assistant","content":"final answer","tool_calls":None,"function_calls":None,"reasoning_content":"reasoning summary"}
        delta={"role":None,"content":"final answer","tool_calls":None,"function_calls":None,"reasoning_content":"reasoning summary"}
        return httpx.Response(200,json={"object":"chat.completion","choices":[{"index":0,"delta":delta,"finish_reason":"stop","message":message}],"usage":{}})

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider_id=_provider(client,"https://nullable-tools.invalid/v1")
    upstream_model=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":"nullable-tools","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"nullable-tools-{uuid4().hex}","enabled_protocols":["openai_chat","anthropic_messages","gemini_v1beta"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream_model["id"]})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}

    response=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert response.status_code==200,response.text
    message=response.json()["choices"][0]["message"]
    assert message["content"]=="final answer" and message["reasoning_content"]=="reasoning summary"
    response=client.post("/v1/chat/completions",headers=headers,json={**payload,"stream":True})
    assert response.status_code==200
    assert '"reasoning_content":"reasoning summary"' in response.text
    assert '"content":"final answer"' in response.text

    anthropic_payload={"model":unified["name"],"max_tokens":64,"messages":[{"role":"user","content":"hello"}]}
    response=client.post("/v1/messages",headers=headers,json=anthropic_payload)
    assert response.status_code==200,response.text
    content=response.json()["content"]
    assert content[0]["type"]=="thinking" and content[0]["thinking"]=="reasoning summary"
    assert content[0]["signature"].startswith("apiswitch_v1_")
    assert content[1]=={"type":"text","text":"final answer"}

    follow_up={"model":unified["name"],"max_tokens":64,"messages":[{"role":"assistant","content":content},{"role":"user","content":"continue"}]}
    response=client.post("/v1/messages",headers=headers,json=follow_up)
    assert response.status_code==200,response.text
    assistant=next(item for item in upstream_requests[-1]["messages"] if item["role"]=="assistant")
    assert assistant["reasoning_content"]=="reasoning summary"
    assert assistant["content"]=="final answer"

    response=client.post("/v1/messages",headers=headers,json={**anthropic_payload,"stream":True})
    assert response.status_code==200,response.text
    assert '"type":"thinking_delta","thinking":"reasoning summary"' in response.text
    assert '"type":"signature_delta","signature":"apiswitch_v1_' in response.text
    assert '"type":"text_delta","text":"final answer"' in response.text

    gemini_payload={"contents":[{"role":"user","parts":[{"text":"hello"}]}]}
    response=client.post(f"/v1beta/models/{unified['name']}:generateContent",headers=headers,json=gemini_payload)
    assert response.status_code==200,response.text
    parts=response.json()["candidates"][0]["content"]["parts"]
    assert parts[0]=={"text":"reasoning summary","thought":True}
    assert parts[1]=={"text":"final answer"}


def test_anthropic_ingress_is_normalized_and_zero_output_empty_completion_is_retried(client:TestClient,monkeypatch):
    captured=[]
    def upstream(request:httpx.Request)->httpx.Response:
        captured.append(json.loads(request.content))
        if len(captured)==1:
            return httpx.Response(200,json={"id":"empty","object":"chat.completion","choices":None,"usage":{"prompt_tokens":12,"completion_tokens":0,"total_tokens":12}})
        return httpx.Response(200,json={"id":"ok","object":"chat.completion","choices":[{"message":{"role":"assistant","content":"你好"},"finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":1,"total_tokens":13}})

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider_id=_provider(client,"https://normalized-anthropic.invalid/v1")
    upstream_model=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":"normalized","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"normalized-{uuid4().hex}","enabled_protocols":["anthropic_messages"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream_model["id"]})
    payload={
        "model":unified["name"],"max_tokens":4096,"temperature":0.6,"top_p":0.9,"stop_sequences":["END"],"stream":True,
        "system":[{"type":"text","text":"system text"}],
        "messages":[{"role":"user","content":[{"type":"text","text":"你好"}]}],
    }
    response=client.post("/v1/messages",headers=_token(client),json=payload)
    assert response.status_code==200,response.text
    assert len(captured)==2
    assert captured[0]==captured[1]
    assert captured[0]["stream"] is False
    assert captured[0]["messages"]==[{"role":"system","content":"system text"},{"role":"user","content":"你好"}]
    assert {key:captured[0][key] for key in ("max_tokens","temperature","top_p","stop")}=={"max_tokens":4096,"temperature":0.6,"top_p":0.9,"stop":["END"]}
    assert '"type":"text_delta","text":"你好"' in response.text


def test_plural_upstream_error_is_preserved_and_does_not_trip_breaker(client: TestClient, monkeypatch):
    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(lambda _: httpx.Response(200, json={
        "errors": {"message": "simulated model is not enabled for API inference", "request_id": "safe-simulated-id"},
    })))
    provider_id = _provider(client, "https://plural-error.invalid/v1")
    upstream_model = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={"model_id": "unsupported-simulated", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": f"plural-error-{uuid4().hex}", "enabled_protocols": ["openai_chat"]},
    ).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_model["id"]})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}

    for _ in range(4):
        response=client.post("/v1/chat/completions",headers=headers,json=payload)
        assert response.status_code==400
        error=response.json()["error"]
        assert error["type"]=="upstream_response_error"
        assert error["stage"]=="upstream_response"
        assert "not enabled for API inference" in error["message"]
        assert error["details"]["error_envelope"]=="errors"
    breaker=next(row for row in client.get("/api/admin/router/status").json()["circuit_breakers"] if row["upstream_model_id"]==upstream_model["id"])
    assert breaker["state"]=="closed" and breaker["consecutive_failures"]==0
    log=client.get("/api/admin/logs").json()[0]
    assert log["error_type"]=="upstream_response_error"
    assert log["failure_stage"]=="upstream_response"


def test_invalid_response_reports_structure_without_values(client: TestClient, monkeypatch):
    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(lambda _: httpx.Response(200, json={
        "unexpected": {"secretish": "must-not-be-returned"}, "items": [{"kind": "unknown"}],
    })))
    provider_id=_provider(client,"https://shape.invalid/v1")
    upstream_model=client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":"shape","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"shape-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream_model["id"]})

    response=client.post("/v1/chat/completions",headers=_token(client),json={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]})
    error=response.json()["error"]
    assert error["type"]=="invalid_upstream_response" and error["stage"]=="upstream_response"
    assert error["details"]["response_shape"]=={"unexpected":{"secretish":"str"},"items":[{"kind":"str"}]}
    assert "must-not-be-returned" not in response.text


def test_all_open_breakers_report_provider_unavailable_and_log_reasons(client: TestClient, monkeypatch):
    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(lambda _: httpx.Response(503, json={"error": {"message": "simulated"}})))
    provider_id = _provider(client, "https://breaker-only.invalid/v1")
    upstream_model = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={"model_id": "breaker-only", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": f"breaker-only-{uuid4().hex}", "enabled_protocols": ["openai_chat"]},
    ).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_model["id"]})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}

    for _ in range(3):
        assert client.post("/v1/chat/completions", headers=headers, json=payload).status_code == 400
    blocked = client.post("/v1/chat/completions", headers=headers, json=payload)
    assert blocked.status_code == 400
    assert blocked.json()["error"]["type"] == "provider_unavailable"
    assert blocked.json()["error"]["stage"] == "circuit_breaker"
    assert blocked.json()["error"]["details"]["candidates"][0]["reasons"] == ["熔断器已开启"]
    log = client.get("/api/admin/logs").json()[0]
    assert log["candidate_summary"][0]["reasons"] == ["熔断器已开启"]


def test_runtime_upstream_failure_falls_through_candidates_of_same_unified_model(client: TestClient, monkeypatch):
    attempted_models = []

    def upstream(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]; attempted_models.append(model)
        if model == "first-candidate": return httpx.Response(503, json={"error": "simulated"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "fallback succeeded"}}], "usage": {}})

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://fallback.invalid/v1")
    models = []
    for model_id in ("first-candidate", "second-candidate"):
        models.append(client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models", json={"model_id": model_id, "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]}).json())
    unified = client.post("/api/admin/unified-models", json={"name": f"fallback-{uuid4().hex}", "enabled_protocols": ["openai_chat"], "combo_strategy": "priority"}).json()
    for priority, model in enumerate(models, start=1):
        client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": model["id"], "priority": priority})

    response = client.post("/v1/chat/completions", headers=_token(client), json={"model": unified["name"], "messages": [{"role": "user", "content": "hello"}]})

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "fallback succeeded"
    assert attempted_models == ["first-candidate", "second-candidate"]
    log = client.get("/api/admin/logs").json()[0]
    assert log["upstream_model_id"] == models[1]["id"]
    assert any("运行时失败" in reason for item in log["candidate_summary"] for reason in item.get("reasons", []))


def test_one_gemini_call_falls_back_from_http_400_to_wrapped_openai_response(client:TestClient,monkeypatch):
    attempted_models=[]
    def upstream(request:httpx.Request)->httpx.Response:
        model=json.loads(request.content)["model"];attempted_models.append(model)
        if model=="nvidia-candidate":return httpx.Response(400,json={"error":{"message":"simulated bad request"}})
        return httpx.Response(200,json={"output":{"data":{"choices":[{"message":{"role":"assistant","content":[{"type":"reasoning","text":"safe reasoning"},{"type":"text","text":"wrapped fallback succeeded"}]},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":2}}}})

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    first_provider=_provider(client,"https://nvidia.invalid/v1")
    second_provider=_provider(client,"https://modelscope.invalid/v1")
    first=client.post(f"/api/admin/provider-instances/{first_provider}/upstream-models",json={"model_id":"nvidia-candidate","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    second=client.post(f"/api/admin/provider-instances/{second_provider}/upstream-models",json={"model_id":"modelscope-candidate","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"gemini-fallback-{uuid4().hex}","enabled_protocols":["gemini_v1beta"],"combo_strategy":"priority"}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":first["id"],"priority":1})
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":second["id"],"priority":2})

    response=client.post(f"/v1beta/models/{unified['name']}:generateContent",headers=_token(client),json={"contents":[{"role":"user","parts":[{"text":"hello"}]}]})
    assert response.status_code==200,response.text
    assert response.json()["candidates"][0]["content"]["parts"][-1]["text"]=="wrapped fallback succeeded"
    assert attempted_models==["nvidia-candidate","modelscope-candidate"]
    logs=[row for row in client.get("/api/admin/logs").json() if row["unified_model"]==unified["name"]]
    assert len(logs)==1 and logs[0]["success"] is True and logs[0]["upstream_model_id"]==second["id"]
    failed_attempt=next(item for item in logs[0]["candidate_summary"] if item.get("reasons")==["运行时失败：upstream_http_error"])
    assert failed_attempt["details"]["status_code"]==400


def test_circuit_breaker_opens_skips_then_half_open_probe_closes(client: TestClient, monkeypatch):
    attempted_models=[]
    first_recovers=False

    def upstream(request:httpx.Request)->httpx.Response:
        model=json.loads(request.content)["model"];attempted_models.append(model)
        if model=="breaker-first" and not first_recovers:
            return httpx.Response(503,json={"error":"simulated"})
        return httpx.Response(200,json={"choices":[{"message":{"content":"ok"}}],"usage":{}})

    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider_id=_provider(client,"https://breaker.invalid/v1")
    models=[]
    for model_id in ("breaker-first","breaker-second"):
        models.append(client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models",json={"model_id":model_id,"input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json())
    unified=client.post("/api/admin/unified-models",json={"name":f"breaker-{uuid4().hex}","enabled_protocols":["openai_chat"],"combo_strategy":"priority"}).json()
    for priority,model in enumerate(models,start=1):
        client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":model["id"],"priority":priority})
    headers=_token(client);payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}

    for _ in range(3):assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert attempted_models.count("breaker-first")==3
    status=client.get("/api/admin/router/status").json()
    breaker=next(row for row in status["circuit_breakers"] if row["upstream_model_id"]==models[0]["id"])
    assert breaker["state"]=="open" and breaker["consecutive_failures"]==3

    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert attempted_models.count("breaker-first")==3

    from datetime import timedelta
    from apiswitch.db.base import utc_now
    with SessionLocal() as db:
        row=db.scalar(select(CircuitBreaker).where(CircuitBreaker.upstream_model_id==models[0]["id"]))
        row.opened_at=utc_now()-timedelta(seconds=row.cooldown_seconds+1);db.commit()
    first_recovers=True
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert attempted_models[-1]=="breaker-first"
    breaker=next(row for row in client.get("/api/admin/router/status").json()["circuit_breakers"] if row["upstream_model_id"]==models[0]["id"])
    assert breaker["state"]=="closed" and breaker["consecutive_failures"]==0


def test_provider_connection_test_and_remote_model_sync_use_http_catalog(client: TestClient, monkeypatch):
    requests = []

    def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET" and request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "catalog-a"}, {"id": "catalog-b", "display_name": "Catalog B"}]})

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://catalog.invalid/v1")

    discovered = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models/discover")
    assert discovered.status_code == 200
    assert [item["model_id"] for item in discovered.json()["models"]] == ["catalog-a", "catalog-b"]
    assert client.get(f"/api/admin/provider-instances/{provider_id}/upstream-models").json() == []

    tested = client.post(f"/api/admin/provider-instances/{provider_id}/test")
    synced = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models/sync")

    assert tested.status_code == 200 and tested.json()["mode"] == "remote" and tested.json()["model_count"] == 2
    assert synced.status_code == 200 and synced.json()["added"] == 2
    models = client.get(f"/api/admin/provider-instances/{provider_id}/upstream-models").json()
    assert [item["model_id"] for item in models] == ["catalog-a", "catalog-b"]
    assert all(request.headers["authorization"] == "Bearer unit-placeholder-credential" for request in requests)


def test_namespaced_model_id_is_preserved_and_legacy_basename_is_repaired(client: TestClient, monkeypatch):
    captured_chat_models = []

    def upstream(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "deepseek-ai/DeepSeek-V4-Flash", "display_name": "DeepSeek-V4-Flash"}]})
        payload = json.loads(request.content)
        captured_chat_models.append(payload["model"])
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "namespaced model worked"}}],
            "usage": {},
        })

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider_id = _provider(client, "https://modelscope.invalid/v1")
    legacy = client.post(
        f"/api/admin/provider-instances/{provider_id}/upstream-models",
        json={"model_id": "DeepSeek-V4-Flash", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": f"namespaced-{uuid4().hex}", "enabled_protocols": ["openai_chat"]},
    ).json()
    client.post(
        f"/api/admin/unified-models/{unified['id']}/candidates",
        json={"upstream_model_id": legacy["id"]},
    )

    discovered = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models/discover")
    assert discovered.status_code == 200
    assert discovered.json()["models"][0]["model_id"] == "deepseek-ai/DeepSeek-V4-Flash"

    synced = client.post(f"/api/admin/provider-instances/{provider_id}/upstream-models/sync")
    assert synced.status_code == 200
    assert synced.json()["updated"] == 1 and synced.json()["added"] == 0
    models = client.get(f"/api/admin/provider-instances/{provider_id}/upstream-models").json()
    assert len(models) == 1
    assert models[0]["id"] == legacy["id"]
    assert models[0]["model_id"] == "deepseek-ai/DeepSeek-V4-Flash"
    candidate = client.get(f"/api/admin/unified-models/{unified['id']}").json()["candidates"][0]
    assert candidate["upstream_model_id"] == legacy["id"]

    response = client.post(
        "/v1/chat/completions",
        headers=_token(client),
        json={"model": unified["name"], "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200, response.text
    assert captured_chat_models == ["deepseek-ai/DeepSeek-V4-Flash"]


def test_sensenova_template_uses_v2_headers_and_forwards_thinking_controls(client: TestClient, monkeypatch):
    captured: list[tuple[httpx.Request, dict]] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append((request, payload))
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "ok", "reasoning_content": "thought"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        })

    monkeypatch.setattr(executor, "HTTP_TRANSPORT", httpx.MockTransport(upstream))
    provider = client.post("/api/admin/provider-instances", json={
        "name": f"sensenova-{uuid4().hex}", "template_key": "sensenova",
        "api_key": "unit-placeholder-credential",
    }).json()
    upstream_model = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "deepseek-v4-flash", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post("/api/admin/unified-models", json={
        "name": f"sensenova-route-{uuid4().hex}", "enabled_protocols": ["openai_chat"],
    }).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream_model["id"]})

    response = client.post("/v1/chat/completions", headers=_token(client), json={
        "model": unified["name"], "messages": [{"role": "user", "content": "hello"}],
        "reasoning_effort": "medium", "max_completion_tokens": 16,
    })

    assert response.status_code == 200, response.text
    request, payload = captured[0]
    assert request.url.path == "/compatible-mode/v2/chat/completions"
    assert request.headers["authorization"] == "Bearer unit-placeholder-credential"
    assert request.headers["accept"] == "application/json"
    assert payload["reasoning_effort"] == "medium"
    assert payload["max_completion_tokens"] == 16
    assert "max_tokens" not in payload

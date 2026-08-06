from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from apiswitch.protocols.canonical import CanonicalRequest, CanonicalResponse
from apiswitch.routing import executor
from apiswitch.routing.engine import RouteCandidate


def _universal_route(client:TestClient):
    main_provider=client.post("/api/admin/provider-instances",json={"name":f"main-{uuid4().hex}","template_key":"openai","base_url":"https://main.invalid/v1"}).json()
    main=client.post(f"/api/admin/provider-instances/{main_provider['id']}/upstream-models",json={"model_id":"universal-main","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    auxiliary=client.post(f"/api/admin/provider-instances/{main_provider['id']}/upstream-models",json={"model_id":"universal-vision","input_capabilities_json":["text","vision"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"universal-{uuid4().hex}","enabled_protocols":["openai_chat","openai_responses","anthropic_messages","gemini_v1beta"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":main["id"]})
    client.post("/api/admin/auxiliary/models",json={"upstream_model_id":auxiliary["id"],"capabilities":["vision"],"priority":1})
    client.post("/api/admin/auxiliary/workflows",json={"workflow_type":"vision_to_text","input_capability":"vision","output_capability":"text"})
    token=client.post("/api/admin/tokens",json={"name":"universal-client","unified_model_ids":[unified["id"]]}).json()["token"]
    return unified,{"Authorization":f"Bearer {token}"}


PROTOCOL_CASES=[
    ("/v1/chat/completions",lambda model:{"model":model,"messages":[{"role":"user","content":[{"type":"text","text":"describe"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]}]}),
    ("/v1/responses",lambda model:{"model":model,"input":[{"role":"user","content":[{"type":"input_text","text":"describe"},{"type":"input_image","image_url":"data:image/png;base64,AA=="}]}]}),
    ("/v1/messages",lambda model:{"model":model,"max_tokens":32,"messages":[{"role":"user","content":[{"type":"text","text":"describe"},{"type":"image","source":{"type":"base64","media_type":"image/png","data":"AA=="}}]}]}),
    ("/v1beta/models/{model}:generateContent",lambda model:{"contents":[{"role":"user","parts":[{"text":"describe"},{"inlineData":{"mimeType":"image/png","data":"AA=="}}]}]}),
]


@pytest.mark.parametrize("endpoint,payload_factory",PROTOCOL_CASES)
def test_vision_assistance_is_protocol_agnostic(client:TestClient,monkeypatch,endpoint,payload_factory):
    executor._clear_auxiliary_runtime_state();unified,headers=_universal_route(client);calls=[]
    def upstream(request:httpx.Request)->httpx.Response:
        payload=json.loads(request.content);calls.append(payload)
        text="red apple description" if payload.get("model")=="universal-vision" else "main answer"
        return httpx.Response(200,json={"choices":[{"message":{"content":text},"finish_reason":"stop"}],"usage":{}})
    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    url=endpoint.format(model=unified["name"]);response=client.post(url,headers=headers,json=payload_factory(unified["name"]))
    assert response.status_code==200,response.text
    helper_payload=next(item for item in calls if item.get("model")=="universal-vision")
    helper_message=next(item for item in helper_payload["messages"] if isinstance(item.get("content"),list))
    helper_image=next(part for part in helper_message["content"] if part.get("type")=="image_url")
    assert helper_image["image_url"]=={"url":"data:image/png;base64,AA=="}
    main_payload=next(item for item in calls if item.get("model")=="universal-main")
    serialized=json.dumps(main_payload,ensure_ascii=False)
    assert "APISwitch 图像辅助识别结果" in serialized
    assert "base64,AA==" not in serialized


def test_auxiliary_candidate_falls_back_after_rate_limit(client:TestClient,monkeypatch):
    executor._clear_auxiliary_runtime_state()
    main_provider=client.post("/api/admin/provider-instances",json={"name":f"fallback-{uuid4().hex}","template_key":"openai","base_url":"https://fallback.invalid/v1"}).json()
    models=[]
    for model_id,caps in (("fallback-main",["text"]),("limited-vision",["text","vision"]),("backup-vision",["text","vision"])):
        models.append(client.post(f"/api/admin/provider-instances/{main_provider['id']}/upstream-models",json={"model_id":model_id,"input_capabilities_json":caps,"output_capabilities_json":["text"]}).json())
    unified=client.post("/api/admin/unified-models",json={"name":f"fallback-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":models[0]["id"]})
    client.post("/api/admin/auxiliary/models",json={"upstream_model_id":models[1]["id"],"capabilities":["vision"],"priority":1})
    client.post("/api/admin/auxiliary/models",json={"upstream_model_id":models[2]["id"],"capabilities":["vision"],"priority":2})
    client.post("/api/admin/auxiliary/workflows",json={"workflow_type":"vision_to_text","input_capability":"vision","output_capability":"text"})
    token=client.post("/api/admin/tokens",json={"name":"fallback-client","unified_model_ids":[unified["id"]]}).json()["token"];called=[]
    def upstream(request:httpx.Request)->httpx.Response:
        payload=json.loads(request.content);called.append(payload["model"])
        if payload["model"]=="limited-vision":return httpx.Response(429,json={"error":{"message":"rate limited"}})
        return httpx.Response(200,json={"choices":[{"message":{"content":"backup description" if payload["model"]=="backup-vision" else "answer"},"finish_reason":"stop"}],"usage":{}})
    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    response=client.post("/v1/chat/completions",headers={"Authorization":f"Bearer {token}"},json={"model":unified["name"],"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]}]})
    assert response.status_code==200,response.text
    assert called==["limited-vision","backup-vision","fallback-main"]
    main_log=next(item for item in client.get("/api/admin/logs").json() if item["request_kind"]=="main")
    step=main_log["auxiliary_summary"]["steps"][0]
    assert [item["status"] for item in step["attempts"]]==["failed","succeeded"]
    assert step["upstream_model_id"]==models[2]["id"]
    executor._clear_auxiliary_runtime_state();called.clear()
    retry=client.post("/v1/chat/completions",headers={"Authorization":f"Bearer {token}"},json={"model":unified["name"],"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]}]})
    assert retry.status_code==200,retry.text
    assert called==["backup-vision","fallback-main"]


def test_native_vision_candidate_does_not_depend_on_auxiliary_model(client:TestClient,monkeypatch):
    executor._clear_auxiliary_runtime_state()
    provider=client.post("/api/admin/provider-instances",json={"name":f"native-{uuid4().hex}","template_key":"openai","base_url":"mock://native"}).json()
    native=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"native-vision","input_capabilities_json":["text","vision"],"output_capabilities_json":["text"]}).json()
    helper=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"unneeded-helper","input_capabilities_json":["text","vision"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"native-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":native["id"]})
    client.post("/api/admin/auxiliary/models",json={"upstream_model_id":helper["id"],"capabilities":["vision"]})
    client.post("/api/admin/auxiliary/workflows",json={"workflow_type":"vision_to_text","input_capability":"vision","output_capability":"text"})
    token=client.post("/api/admin/tokens",json={"name":"native-client","unified_model_ids":[unified["id"]]}).json()["token"];called=[];original=executor._call_http
    async def capture(candidate,request):called.append(candidate.upstream.model_id);return await original(candidate,request)
    monkeypatch.setattr(executor,"_call_http",capture)
    response=client.post("/v1/chat/completions",headers={"Authorization":f"Bearer {token}"},json={"model":unified["name"],"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]}]})
    assert response.status_code==200,response.text
    assert called==["native-vision"]
    main_log=next(item for item in client.get("/api/admin/logs").json() if item["request_kind"]=="main")
    assert main_log["auxiliary_summary"]["steps"]==[]


@pytest.mark.asyncio
async def test_identical_auxiliary_calls_are_coalesced_and_cached(monkeypatch):
    executor._clear_auxiliary_runtime_state();calls=0
    async def call(candidate,request):
        nonlocal calls;calls+=1;await asyncio.sleep(0.02)
        return CanonicalResponse(text="shared vision",usage={"prompt_tokens":10})
    monkeypatch.setattr(executor,"_call_http",call)
    candidate=RouteCandidate(SimpleNamespace(id=1,priority=1),SimpleNamespace(id=10,model_id="shared-model"),SimpleNamespace(id=20,protocol_type="openai_compatible"),[])
    request=CanonicalRequest("chat","openai_chat","ignored",messages=[{"role":"user","content":"same"}])
    first,second=await asyncio.gather(
        executor._call_auxiliary_shared(candidate,request,source_request_id="a",require_text=True),
        executor._call_auxiliary_shared(candidate,request,source_request_id="b",require_text=True),
    )
    third=await executor._call_auxiliary_shared(candidate,request,source_request_id="c",require_text=True)
    assert calls==1
    assert {first[1]["cache_status"],second[1]["cache_status"]}=={"miss","coalesced"}
    assert third[1]["cache_status"]=="hit"
    assert sum(int(item[0].usage.get("prompt_tokens") or 0) for item in (first,second,third))==10

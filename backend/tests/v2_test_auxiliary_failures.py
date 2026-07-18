from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from apiswitch.routing import executor


CASES=[
    ("vision_to_text","vision","text",lambda model:{"model":model,"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]}]}),
    ("file_extract","files","text",lambda model:{"model":model,"messages":[{"role":"user","content":[{"type":"input_file","file_id":"file_mock"}]}]}),
    ("context_compress","long_context","text",lambda model:{"model":model,"messages":[{"role":"user","content":"x"*32001}]}),
    ("tool_plan","tools","tool_results",lambda model:{"model":model,"messages":[{"role":"user","content":"plan"}],"tools":[{"type":"function","function":{"name":"lookup","parameters":{"type":"object"}}}]}),
    ("audio_transcribe","audio","text",lambda model:{"model":model,"messages":[{"role":"user","content":[{"type":"input_audio","input_audio":{"data":"AA==","format":"wav"}}]}]}),
    ("structured_repair","json","json",lambda model:{"model":model,"messages":[{"role":"user","content":"json"}],"response_format":{"type":"json_object"}}),
    ("terminal_capability","embeddings","embeddings",lambda model:{"model":model,"input":"embed"}),
]


def _route(client,workflow_type,input_capability,output_capability,*,configure_aux:bool=True,aux_protocol="openai_compatible"):
    main_provider=client.post("/api/admin/provider-instances",json={"name":f"main-{uuid4().hex}","template_key":"openai","base_url":"mock://main"}).json()
    main=client.post(f"/api/admin/provider-instances/{main_provider['id']}/upstream-models",json={"model_id":"main-text","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    aux_provider=client.post("/api/admin/provider-instances",json={"name":f"aux-{uuid4().hex}","template_key":"manual","protocol_type":aux_protocol,"base_url":"https://auxiliary.invalid/v1"}).json()
    auxiliary=client.post(f"/api/admin/provider-instances/{aux_provider['id']}/upstream-models",json={"model_id":"aux-model","input_capabilities_json":[input_capability,"text"],"output_capabilities_json":[output_capability,"text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"aux-route-{uuid4().hex}","enabled_protocols":["openai_chat","embeddings"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":main["id"]})
    if configure_aux:client.post("/api/admin/auxiliary/models",json={"upstream_model_id":auxiliary["id"],"capabilities":[input_capability],"priority":1})
    client.post("/api/admin/auxiliary/workflows",json={"workflow_type":workflow_type,"input_capability":input_capability,"output_capability":output_capability,"ordered_steps":[{"input":input_capability,"output":output_capability,"timeout_seconds":1}]})
    token=client.post("/api/admin/tokens",json={"name":"aux-failure","unified_model_ids":[unified["id"]]}).json()["token"]
    endpoint="/v1/embeddings" if workflow_type=="terminal_capability" else "/v1/chat/completions"
    return unified,endpoint,{"Authorization":f"Bearer {token}"}


@pytest.mark.parametrize("workflow_type,input_capability,output_capability,payload_factory",CASES)
def test_every_workflow_missing_configuration_fails_before_any_upstream(client,monkeypatch,workflow_type,input_capability,output_capability,payload_factory):
    calls=[];monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(lambda request:(calls.append(request),httpx.Response(200,json={}))[1]))
    unified,endpoint,headers=_route(client,workflow_type,input_capability,output_capability,configure_aux=False)
    response=client.post(endpoint,headers=headers,json=payload_factory(unified["name"]))
    assert response.status_code==400 and response.json()["error"]["type"]=="auxiliary_workflow_not_configured"
    assert calls==[]


@pytest.mark.parametrize("failure",["timeout","http_error","incompatible"])
@pytest.mark.parametrize("workflow_type,input_capability,output_capability,payload_factory",CASES)
def test_every_workflow_stops_on_timeout_upstream_failure_or_incompatibility(client,monkeypatch,failure,workflow_type,input_capability,output_capability,payload_factory):
    calls=[]
    def upstream(request:httpx.Request)->httpx.Response:
        calls.append(json.loads(request.content));model=calls[-1].get("model")
        if model=="aux-model":
            if failure=="timeout":raise httpx.ReadTimeout("simulated",request=request)
            return httpx.Response(503,json={"error":"simulated"})
        return httpx.Response(200,json={"choices":[{"message":{"content":"main"}}],"usage":{}})
    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    unified,endpoint,headers=_route(client,workflow_type,input_capability,output_capability,aux_protocol="custom" if failure=="incompatible" else "openai_compatible")
    response=client.post(endpoint,headers=headers,json=payload_factory(unified["name"]))
    assert response.status_code==400,response.text
    error=response.json()["error"];assert error["type"]=="auxiliary_step_failed" and error["stage"]=="auxiliary_step"
    expected={"timeout":"provider_timeout","http_error":"upstream_http_error","incompatible":"protocol_conversion_unsupported"}[failure]
    assert error["details"]["cause"]==expected
    assert all(item.get("model")=="aux-model" for item in calls)
    assert len(calls)==(0 if failure=="incompatible" else 1)
    log=client.get("/api/admin/logs").json()[0]
    assert log["failure_stage"]=="auxiliary_step"


def test_per_unified_model_mode_executes_only_scoped_auxiliary_configuration(client,monkeypatch):
    def upstream(request:httpx.Request)->httpx.Response:
        return httpx.Response(200,json={"choices":[{"message":{"content":"vision description"}}],"usage":{}})
    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    unified,endpoint,headers=_route(client,"vision_to_text","vision","text")
    aux=client.get("/api/admin/auxiliary/models").json()[0]
    workflow=client.get("/api/admin/auxiliary/workflows").json()[0]
    client.patch(f"/api/admin/auxiliary/models/{aux['id']}",json={"unified_model_id":unified["id"]})
    client.patch(f"/api/admin/auxiliary/workflows/{workflow['id']}",json={"scope":"unified_model","unified_model_id":unified["id"]})
    client.patch("/api/admin/auxiliary/settings",json={"mode":"per_unified_model"})
    response=client.post(endpoint,headers=headers,json=CASES[0][3](unified["name"]))
    assert response.status_code==200,response.text
    assert client.get("/api/admin/logs").json()[0]["auxiliary_summary"]["mode"]=="per_unified_model"


def test_disabled_auxiliary_mode_rejects_capability_gap_without_calling_auxiliary(client,monkeypatch):
    calls=[];monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(lambda request:(calls.append(request),httpx.Response(200,json={}))[1]))
    unified,endpoint,headers=_route(client,"vision_to_text","vision","text")
    client.patch("/api/admin/auxiliary/settings",json={"mode":"disabled"})
    response=client.post(endpoint,headers=headers,json=CASES[0][3](unified["name"]))
    assert response.status_code==400 and response.json()["error"]["type"]=="capability_not_supported"
    assert calls==[]

from __future__ import annotations

import json
from uuid import uuid4

import httpx

from apiswitch.routing import executor


def _route(client,monkeypatch):
    captured=[]
    def upstream(request:httpx.Request)->httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={"choices":[{"message":{"role":"assistant","content":None,"tool_calls":[{"id":"call_weather","type":"function","function":{"name":"weather","arguments":"{\"city\":\"Shanghai\"}"}}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":5,"completion_tokens":4}})
    monkeypatch.setattr(executor,"HTTP_TRANSPORT",httpx.MockTransport(upstream))
    provider=client.post("/api/admin/provider-instances",json={"name":f"tools-{uuid4().hex}","template_key":"openai","base_url":"https://tools.invalid/v1","api_key":"unit-placeholder"}).json()
    model=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"tool-model","input_capabilities_json":["text"],"output_capabilities_json":["text","tools"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"tool-route-{uuid4().hex}","enabled_protocols":["openai_chat","openai_responses","anthropic_messages","gemini_v1beta"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":model["id"]})
    token=client.post("/api/admin/tokens",json={"name":"tool-client","unified_model_ids":[unified["id"]]}).json()["token"]
    return unified["name"],{"Authorization":f"Bearer {token}"},captured


def test_tool_definitions_calls_and_results_survive_all_chat_response_adapters(client,monkeypatch):
    model,headers,captured=_route(client,monkeypatch)
    definition={"type":"function","function":{"name":"weather","description":"lookup","parameters":{"type":"object","properties":{"city":{"type":"string"}}}}}
    chat=client.post("/v1/chat/completions",headers=headers,json={"model":model,"messages":[{"role":"user","content":"weather"}],"tools":[definition],"tool_choice":"required"})
    assert chat.status_code==200
    assert chat.json()["choices"][0]["message"]["tool_calls"][0]["function"]["name"]=="weather"
    assert captured[-1]["tools"][0]["function"]["parameters"]["type"]=="object"

    responses=client.post("/v1/responses",headers=headers,json={"model":model,"input":"weather","tools":[{"type":"function","name":"weather","parameters":{"type":"object"}}]})
    assert any(item["type"]=="function_call" and item["name"]=="weather" for item in responses.json()["output"])

    responses_followup=client.post("/v1/responses",headers=headers,json={"model":model,"input":[
        {"type":"function_call","call_id":"call_weather","name":"weather","arguments":"{\"city\":\"Shanghai\"}"},
        {"type":"function_call_output","call_id":"call_weather","output":"sunny"},
    ],"tools":[{"type":"function","name":"weather","parameters":{"type":"object"}}],"reasoning":{"effort":"medium"}})
    assert responses_followup.status_code==200
    assert captured[-1]["messages"][0]["tool_calls"][0]["id"]=="call_weather"
    assert captured[-1]["messages"][1]=={"role":"tool","tool_call_id":"call_weather","content":"sunny"}
    assert captured[-1]["reasoning_effort"]=="medium"

    anthropic=client.post("/v1/messages",headers=headers,json={"model":model,"max_tokens":20,"messages":[{"role":"user","content":"weather"}],"tools":[{"name":"weather","input_schema":{"type":"object"}}],"tool_choice":{"type":"tool","name":"weather"}})
    block=next(item for item in anthropic.json()["content"] if item["type"]=="tool_use")
    assert block["input"]=={"city":"Shanghai"}
    assert captured[-1]["tool_choice"]=={"type":"function","function":{"name":"weather"}}

    gemini=client.post(f"/v1beta/models/{model}:generateContent",headers=headers,json={"contents":[{"parts":[{"text":"weather"}]}],"tools":[{"functionDeclarations":[{"name":"weather","parameters":{"type":"object"}}]}]})
    function_call=gemini.json()["candidates"][0]["content"]["parts"][0]["functionCall"]
    assert function_call["name"]=="weather" and function_call["args"]["city"]=="Shanghai"

    followup=client.post("/v1/messages",headers=headers,json={"model":model,"max_tokens":20,"messages":[{"role":"assistant","content":[{"type":"tool_use","id":"call_weather","name":"weather","input":{"city":"Shanghai"}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"call_weather","content":"sunny"}]}],"tools":[{"name":"weather","input_schema":{"type":"object"}}]})
    assert followup.status_code==200
    assert captured[-1]["messages"][0]["tool_calls"][0]["function"]["name"]=="weather"
    assert captured[-1]["messages"][1]=={"role":"tool","tool_call_id":"call_weather","content":"sunny"}

    gemini_followup=client.post(f"/v1beta/models/{model}:generateContent",headers=headers,json={"contents":[{"role":"model","parts":[{"functionCall":{"name":"weather","args":{"city":"Shanghai"}}}]},{"role":"user","parts":[{"functionResponse":{"name":"weather","response":{"result":"sunny"}}}]}],"tools":[{"functionDeclarations":[{"name":"weather","parameters":{"type":"object"}}]}]})
    assert gemini_followup.status_code==200
    assert captured[-1]["messages"][0]["tool_calls"][0]["function"]["name"]=="weather"
    assert captured[-1]["messages"][1]["role"]=="tool"


def test_tool_calls_use_canonical_tool_delta_for_sse_and_websocket(client,monkeypatch):
    model,headers,_=_route(client,monkeypatch)
    definition={"type":"function","function":{"name":"weather","parameters":{"type":"object"}}}
    streamed=client.post("/v1/chat/completions",headers=headers,json={"model":model,"messages":[{"role":"user","content":"weather"}],"tools":[definition],"stream":True})
    assert streamed.status_code==200 and '"tool_calls"' in streamed.text and '"name":"weather"' in streamed.text
    gemini=client.post(
        f"/v1beta/models/{model}:streamGenerateContent",
        headers=headers,
        json={"contents":[{"parts":[{"text":"weather"}]}],"tools":[{"functionDeclarations":[{"name":"weather","parameters":{"type":"object"}}]}]},
    )
    assert gemini.status_code==200
    assert gemini.headers["content-type"].startswith("text/event-stream")
    assert gemini.text.startswith("data: ")
    assert '"functionCall":{"name":"weather","args":{"city":"Shanghai"}}' in gemini.text
    assert '"finishReason":"STOP"' in gemini.text
    with client.websocket_connect("/v1/ws/chat/completions",headers=headers) as socket:
        socket.send_json({"model":model,"messages":[{"role":"user","content":"weather"}],"tools":[definition]})
        assert socket.receive_json()["event"]=="start"
        tool=socket.receive_json();assert tool["event"]=="tool_delta" and tool["data"]["name"]=="weather"
        assert socket.receive_json()["event"]=="completed"

"""Loss-aware ingress/egress adapters around a single canonical request type."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


class ProtocolError(ValueError):
    def __init__(self, error_type: str, message: str, stage: str, details: dict[str, Any] | None = None):
        super().__init__(message); self.error_type, self.stage, self.details = error_type, stage, details or {}


@dataclass
class CanonicalEvent:
    event_type: str
    request_id: str
    delta: str | None = None
    response: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    index: int = 0
    finish_reason: str | None = None

    def dump(self) -> dict[str, Any]: return asdict(self)


@dataclass
class CanonicalResponse:
    text: str = ""
    reasoning_content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None
    mock: bool = False
    upstream_url: str | None = None
    binary: bytes | None = None
    media_type: str | None = None

    def get(self,key:str,default:Any=None)->Any:return getattr(self,key,default)
    def __getitem__(self,key:str)->Any:return getattr(self,key)
    def dump(self)->dict[str,Any]:return asdict(self)


@dataclass
class CanonicalRequest:
    request_type: str
    inbound_protocol: str
    unified_model: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    instructions: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: Any = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    required_input: list[str] = field(default_factory=lambda: ["text"])
    required_output: list[str] = field(default_factory=lambda: ["text"])
    stream: bool = False
    session_key: str | None = None

    def dump(self) -> dict[str, Any]: return asdict(self)


def from_openai_chat(payload: dict[str, Any]) -> CanonicalRequest:
    unsupported = set(payload) & {"logprobs", "logit_bias"}
    if unsupported: raise ProtocolError("protocol_conversion_unsupported", "字段无法可靠转换：" + ", ".join(sorted(unsupported)), "protocol_conversion")
    messages = payload.get("messages", [])
    needs = ["text"]
    text_size=0
    for message in messages:
        content = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(content,str):text_size+=len(content)
        parts = content if isinstance(content, list) else []
        if any(isinstance(p, dict) and p.get("type") in {"image_url", "input_image"} for p in parts): needs.append("vision")
        if any(isinstance(p, dict) and p.get("type") in {"input_audio"} for p in parts): needs.append("audio")
        if any(isinstance(p,dict) and p.get("type") in {"input_file","file"} for p in parts):needs.append("files")
        text_size+=sum(len(str(part.get("text",""))) for part in parts if isinstance(part,dict))
    if text_size>32_000:needs.append("long_context")
    output=["tools"] if payload.get("tools") else (["json"] if payload.get("response_format") else ["text"])
    parameters={k:v for k,v in payload.items() if k in {"temperature","top_p","max_tokens","response_format","reasoning_effort","frequency_penalty","presence_penalty","seed","stop"} and v is not None}
    if payload.get("max_completion_tokens") is not None:parameters["max_tokens"]=payload["max_completion_tokens"]
    return CanonicalRequest("chat", "openai_chat", payload.get("model", ""), messages=messages, tools=payload.get("tools", []),tool_choice=payload.get("tool_choice"), parameters=parameters, required_input=list(dict.fromkeys(needs)), required_output=output, stream=bool(payload.get("stream")), session_key=str(payload.get("user")) if payload.get("user") else None)


def from_openai_responses(payload: dict[str, Any]) -> CanonicalRequest:
    source = payload.get("input", "")
    needs = ["text"]
    if isinstance(source, str):
        messages = [{"role": "user", "content": source}]
    elif isinstance(source, list):
        messages = []
        for item in source:
            if not isinstance(item, dict):
                raise ProtocolError("protocol_conversion_unsupported", "Responses input 项无法可靠转换为消息", "protocol_conversion")
            item_type = item.get("type", "message")
            if item_type == "function_call_output":
                messages.append({"role":"tool","tool_call_id":item.get("call_id"),"content":item.get("output","")})
                continue
            if item_type == "function_call":
                messages.append({"role":"assistant","content":None,"tool_calls":[{"id":item.get("call_id") or item.get("id"),"type":"function","function":{"name":item.get("name"),"arguments":item.get("arguments") or "{}"}}]})
                continue
            if item_type == "reasoning":
                summary=item.get("summary") or []
                text="\n".join(str(part.get("text", "")) for part in summary if isinstance(part,dict))
                if text:messages.append({"role":"assistant","content":None,"reasoning_content":text})
                continue
            if item.get("role") not in {"user", "assistant", "system", "developer"}:
                raise ProtocolError("protocol_conversion_unsupported", "Responses input 项无法可靠转换为消息", "protocol_conversion")
            role = "system" if item.get("role") == "developer" else item["role"]
            content=item.get("content", "")
            if isinstance(content,list):
                for part in content:
                    if not isinstance(part,dict):continue
                    kind=part.get("type")
                    if kind in {"input_image","image_url"}:needs.append("vision")
                    elif kind in {"input_file","file"}:needs.append("files")
                    elif kind=="input_audio":needs.append("audio")
            messages.append({"role": role, "content": content})
    else:
        raise ProtocolError("protocol_conversion_unsupported", "Responses input 必须是字符串或消息数组", "protocol_conversion")
    parameters = {key: value for key, value in payload.items() if key in {"temperature", "top_p"}}
    if payload.get("max_output_tokens") is not None:
        parameters["max_tokens"] = payload["max_output_tokens"]
    reasoning=payload.get("reasoning") or {}
    if payload.get("reasoning_effort") is not None:parameters["reasoning_effort"]=payload["reasoning_effort"]
    elif isinstance(reasoning,dict) and reasoning.get("effort") is not None:parameters["reasoning_effort"]=reasoning["effort"]
    metadata=payload.get("metadata") or {};session_key=metadata.get("session_id") or metadata.get("user_id")
    return CanonicalRequest("chat", "openai_responses", payload.get("model", ""), messages=messages, instructions=payload.get("instructions"), tools=payload.get("tools", []),tool_choice=payload.get("tool_choice"), parameters=parameters, required_input=list(dict.fromkeys(needs)),required_output=["tools"] if payload.get("tools") else ["text"], stream=bool(payload.get("stream")), session_key=str(session_key) if session_key else None)


def from_anthropic(payload: dict[str, Any]) -> CanonicalRequest:
    metadata=payload.get("metadata") or {};session_key=metadata.get("user_id")
    needs=["text"]
    for message in payload.get("messages",[]):
        parts=message.get("content",[]) if isinstance(message,dict) else []
        if isinstance(parts,list) and any(isinstance(part,dict) and part.get("type")=="image" for part in parts):needs.append("vision")
        if isinstance(parts,list) and any(isinstance(part,dict) and part.get("type")=="document" for part in parts):needs.append("files")
    parameters={key:payload[key] for key in ("max_tokens","temperature","top_p","top_k") if payload.get(key) is not None}
    if payload.get("stop_sequences") is not None:parameters["stop"]=payload["stop_sequences"]
    thinking=payload.get("thinking")
    if isinstance(thinking,dict) and thinking.get("type")=="enabled":
        parameters["reasoning_effort"]="medium"
        if thinking.get("budget_tokens") is not None:parameters["thinking_budget"]=thinking["budget_tokens"]
    return CanonicalRequest("chat", "anthropic_messages", payload.get("model", ""), messages=payload.get("messages", []), instructions=payload.get("system"), tools=payload.get("tools", []),tool_choice=payload.get("tool_choice"), parameters=parameters, required_input=list(dict.fromkeys(needs)), required_output=["tools"] if payload.get("tools") else ["text"], stream=bool(payload.get("stream")), session_key=str(session_key) if session_key else None)


def from_gemini(model: str, payload: dict[str, Any]) -> CanonicalRequest:
    messages = [{"role": c.get("role", "user"), "content": c.get("parts", [])} for c in payload.get("contents", [])]
    parts=[part for content in payload.get("contents",[]) for part in content.get("parts",[]) if isinstance(part,dict)];needs=["text"]
    for part in parts:
        media=part.get("inlineData") or part.get("inline_data") or {};mime=str(media.get("mimeType") or media.get("mime_type") or "")
        if mime.startswith("image/"):needs.append("vision")
        if mime.startswith("audio/"):needs.append("audio")
        if part.get("fileData") or part.get("file_data"):needs.append("files")
    generation=payload.get("generationConfig") or payload.get("generation_config") or {}
    if not isinstance(generation,dict):
        raise ProtocolError("protocol_conversion_unsupported","generationConfig 必须是对象","protocol_conversion")
    candidate_count=generation.get("candidateCount",generation.get("candidate_count",1))
    if candidate_count not in (None,1):
        raise ProtocolError("protocol_conversion_unsupported","当前统一响应只能无损返回一个 Gemini candidate","protocol_conversion")
    parameters={}
    for source,target in (
        ("temperature","temperature"),("topP","top_p"),("topK","top_k"),
        ("maxOutputTokens","max_tokens"),("stopSequences","stop"),
        ("frequencyPenalty","frequency_penalty"),("presencePenalty","presence_penalty"),
        ("seed","seed"),
    ):
        if generation.get(source) is not None:parameters[target]=generation[source]
    response_mime=generation.get("responseMimeType")
    response_schema=generation.get("responseSchema")
    if response_mime=="application/json":
        parameters["response_format"]={"type":"json_schema","json_schema":{"name":"gemini_response","schema":response_schema}} if response_schema else {"type":"json_object"}
    elif response_mime not in (None,"text/plain"):
        raise ProtocolError("protocol_conversion_unsupported",f"无法可靠转换 responseMimeType={response_mime}","protocol_conversion")
    output=["tools"] if payload.get("tools") else (["json"] if response_mime=="application/json" else ["text"])
    return CanonicalRequest("chat", "gemini_v1beta", model, messages=messages, instructions=(payload.get("systemInstruction") or {}).get("parts", [{}])[0].get("text"), tools=payload.get("tools", []),tool_choice=payload.get("toolConfig"),parameters=parameters, required_input=list(dict.fromkeys(needs)), required_output=output, stream=bool(payload.get("stream",False)))


def from_terminal(protocol: str, request_type: str, payload: dict[str, Any]) -> CanonicalRequest:
    model = payload.get("model", "")
    outputs = {"embeddings": ["embeddings"], "images": ["images"], "audio": ["audio"], "moderations": ["moderation"], "rerank": ["rerank"], "search": ["search"], "video": ["video"], "music": ["music"]}
    return CanonicalRequest(request_type, protocol, model, attachments=payload.get("attachments", []), parameters=payload, required_output=outputs.get(request_type, ["text"]))


def _openai_tool_calls(tool_calls:list[dict[str,Any]])->list[dict[str,Any]]:
    import json
    return [{"id":item.get("id") or f"call_{index}","type":"function","function":{"name":item.get("name","").strip(),"arguments":item.get("arguments") if isinstance(item.get("arguments"),str) else json.dumps(item.get("arguments") or {},ensure_ascii=False,separators=(",",":"))}} for index,item in enumerate(tool_calls)]


def reasoning_signature(request_id: str, reasoning_content: str) -> str:
    """Return a stable, non-secret signature for gateway-created thinking blocks."""
    digest = hashlib.sha256(f"{request_id}\0{reasoning_content}".encode("utf-8")).hexdigest()
    return "apiswitch_v1_" + digest


def to_openai_response(request: CanonicalRequest, response: CanonicalResponse, request_id: str) -> dict[str, Any]:
    message:dict[str,Any]={"role":"assistant","content":response.text or (None if response.tool_calls else "")}
    if response.reasoning_content:message["reasoning_content"]=response.reasoning_content
    if response.tool_calls:message["tool_calls"]=_openai_tool_calls(response.tool_calls)
    return {"id": "chatcmpl_" + request_id, "object": "chat.completion", "model": request.unified_model, "choices": [{"index": 0, "message":message, "finish_reason": "tool_calls" if response.tool_calls else "stop"}],"usage":response.usage or None, "apiswitch": {"request_id": request_id}}


def to_anthropic_response(request: CanonicalRequest, response: CanonicalResponse, request_id: str) -> dict[str, Any]:
    content=[]
    if response.reasoning_content:
        content.append({"type":"thinking","thinking":response.reasoning_content,"signature":reasoning_signature(request_id,response.reasoning_content)})
    if response.text:content.append({"type":"text","text":response.text})
    content.extend({"type":"tool_use","id":item.get("id") or f"toolu_{index}","name":item.get("name","").strip(),"input":item.get("arguments") if isinstance(item.get("arguments"),dict) else {"raw":item.get("arguments")}} for index,item in enumerate(response.tool_calls))
    return {"id": "msg_" + request_id, "type": "message", "role": "assistant", "model": request.unified_model, "content":content, "stop_reason": "tool_use" if response.tool_calls else "end_turn","usage":response.usage or {}}


def to_gemini_response(request: CanonicalRequest, response: CanonicalResponse, request_id: str) -> dict[str, Any]:
    parts=[]
    if response.reasoning_content:parts.append({"text":response.reasoning_content,"thought":True})
    if response.text:parts.append({"text":response.text})
    parts.extend({"functionCall":{"name":item.get("name","").strip(),"args":item.get("arguments") if isinstance(item.get("arguments"),dict) else {"raw":item.get("arguments")}}} for item in response.tool_calls)
    return {"candidates": [{"content": {"role": "model", "parts":parts}, "finishReason": "STOP"}], "modelVersion": request.unified_model, "responseId": request_id,"usageMetadata":response.usage or {}}


def response_events(canonical: CanonicalResponse, request_id: str, response: dict[str, Any]) -> list[CanonicalEvent]:
    """Represent every streamed protocol with the same lossless event sequence."""
    events = [CanonicalEvent("start", request_id)]
    if canonical.reasoning_content:
        events.append(CanonicalEvent("reasoning_delta",request_id,delta=canonical.reasoning_content))
    if canonical.text:
        events.append(CanonicalEvent("content_delta", request_id, delta=canonical.text))
    for index,tool_call in enumerate(canonical.tool_calls):
        events.append(CanonicalEvent("tool_delta",request_id,data=tool_call,index=index))
    events.append(CanonicalEvent("completed", request_id, response=response, finish_reason="stop"))
    return events

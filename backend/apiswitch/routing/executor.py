"""Generation-2 upstream execution.

Routing and protocol conversion stay independent from HTTP transport so tests
can use ``httpx.MockTransport`` without contacting a real provider.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
import uuid
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.catalog.templates import get_template
from apiswitch.db.base import utc_now
from apiswitch.db.models import ApiToken, Budget, CircuitBreaker, ProviderHealth, ProviderInstance, RequestLog, UnifiedModel, UpstreamModel, UsageHistory
from apiswitch.protocols.canonical import CanonicalRequest, CanonicalResponse, ProtocolError
from apiswitch.routing.engine import RouteCandidate, plan_auxiliary, remember_session_candidate, route_candidates
from apiswitch.routing.capabilities import infer_model_characteristics
from apiswitch.security.crypto import SecretCryptoError, secret_crypto
from apiswitch.security.outbound import OutboundURLRejected,validate_outbound_url
from apiswitch.services.budget_enforcement import accumulate_budget_spend, budget_is_exceeded, matching_budgets

HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None
EMPTY_COMPLETION_MAX_ATTEMPTS = 4
EMPTY_COMPLETION_RETRY_BASE_SECONDS = 0.5
AUXILIARY_CACHE_TTL_SECONDS = 60.0
AUXILIARY_CACHE_MAX_ENTRIES = 256

_auxiliary_cache:dict[str,tuple[float,CanonicalResponse,str]]={}
_auxiliary_inflight:dict[tuple[int,str],tuple[asyncio.Task[CanonicalResponse],str]]={}
_auxiliary_runtime_lock=threading.Lock()


def _canonical_tools(request:CanonicalRequest)->list[dict[str,Any]]:
    result=[]
    for group in request.tools:
        if not isinstance(group,dict):raise ProtocolError("protocol_conversion_unsupported","工具定义必须是对象","protocol_conversion")
        declarations=group.get("functionDeclarations") or group.get("function_declarations")
        items=declarations if isinstance(declarations,list) else [group]
        for item in items:
            function=item.get("function") if isinstance(item,dict) else None
            source=function if isinstance(function,dict) else item
            name=source.get("name") if isinstance(source,dict) else None
            if not name:raise ProtocolError("protocol_conversion_unsupported","工具定义缺少函数名","protocol_conversion")
            result.append({"name":str(name),"description":source.get("description"),"parameters":source.get("parameters") or source.get("input_schema") or {"type":"object","properties":{}}})
    return result


def _tools_for_provider(request:CanonicalRequest,protocol:str)->list[dict[str,Any]]:
    tools=_canonical_tools(request)
    if protocol in {"openai","openai_compatible"}:return [{"type":"function","function":tool} for tool in tools]
    if protocol=="anthropic_messages":return [{"name":tool["name"],"description":tool.get("description"),"input_schema":tool["parameters"]} for tool in tools]
    if protocol=="gemini":return [{"functionDeclarations":[tool for tool in tools]}]
    raise ProtocolError("protocol_conversion_unsupported","供应商协议不支持工具定义","protocol_conversion")


def _tool_choice_for_provider(request:CanonicalRequest,protocol:str)->Any:
    choice=request.tool_choice
    if choice is None:return None
    if protocol in {"openai","openai_compatible"}:
        if isinstance(choice,str):return choice
        if request.inbound_protocol=="anthropic_messages" and isinstance(choice,dict):
            kind=choice.get("type")
            if kind in {"auto","none"}:return kind
            if kind=="any":return "required"
            if kind=="tool" and choice.get("name"):return {"type":"function","function":{"name":choice["name"]}}
        if request.inbound_protocol=="gemini_v1beta" and isinstance(choice,dict):
            config=choice.get("functionCallingConfig") or choice.get("function_calling_config") or {};mode=str(config.get("mode","AUTO")).lower()
            if mode in {"auto","none"}:return mode
            if mode in {"any","required"}:return "required"
        if isinstance(choice,dict) and choice.get("type")=="function":return choice
    elif protocol=="anthropic_messages":
        if isinstance(choice,str):return {"type":"any" if choice=="required" else choice}
        if isinstance(choice,dict) and choice.get("type")=="function":return {"type":"tool","name":((choice.get("function") or {}).get("name"))}
        if isinstance(choice,dict) and choice.get("type") in {"auto","any","none","tool"}:return choice
    elif protocol=="gemini":
        if isinstance(choice,str):return {"functionCallingConfig":{"mode":{"required":"ANY","none":"NONE"}.get(choice,"AUTO")}}
        if request.inbound_protocol=="anthropic_messages" and isinstance(choice,dict):
            kind=choice.get("type");config={"mode":"ANY" if kind in {"any","tool"} else ("NONE" if kind=="none" else "AUTO")}
            if kind=="tool" and choice.get("name"):config["allowedFunctionNames"]=[choice["name"]]
            return {"functionCallingConfig":config}
        if isinstance(choice,dict):return choice
    raise ProtocolError("protocol_conversion_unsupported",f"工具选择无法转换为 {protocol}","protocol_conversion")


def _canonical_message_parts(request:CanonicalRequest,message:dict[str,Any])->list[dict[str,Any]]:
    role=message.get("role")
    if request.inbound_protocol in {"openai_chat","openai_responses"}:
        if role=="tool":return [{"type":"tool_result","tool_call_id":message.get("tool_call_id"),"content":message.get("content","")}]
        parts=[];content=message.get("content","")
        if isinstance(content,str):
            if content:parts.append({"type":"text","text":content})
        elif isinstance(content,list):
            for item in content:
                if not isinstance(item,dict):raise ProtocolError("protocol_conversion_unsupported","消息内容项必须是对象","protocol_conversion")
                if item.get("type") in {"text","input_text","output_text"}:parts.append({"type":"text","text":item.get("text","")})
                elif item.get("type") in {"input_image","image_url"}:
                    image_url=item.get("image_url") or item.get("url")
                    if isinstance(image_url,str):image_url={"url":image_url}
                    parts.append({"type":"image","image_url":image_url})
                elif item.get("type") in {"input_file","file"}:parts.append({"type":"file","file":item})
                elif item.get("type")=="input_audio":parts.append({"type":"audio","audio":item.get("input_audio") or item})
                else:raise ProtocolError("protocol_conversion_unsupported",f"{item.get('type','unknown')} 内容无法可靠跨协议转换","protocol_conversion")
        elif content is not None:raise ProtocolError("protocol_conversion_unsupported","消息内容无法可靠跨协议转换","protocol_conversion")
        if message.get("reasoning_content"):parts.append({"type":"reasoning","text":message.get("reasoning_content","")})
        for item in message.get("tool_calls",[]):
            function=item.get("function") or {};parts.append({"type":"tool_call","id":item.get("id"),"name":function.get("name"),"arguments":_tool_arguments(function.get("arguments",{}))})
        return parts
    if request.inbound_protocol=="anthropic_messages":
        content=message.get("content",[]);content=[{"type":"text","text":content}] if isinstance(content,str) else content
        parts=[]
        for item in content:
            if not isinstance(item,dict):raise ProtocolError("protocol_conversion_unsupported","Anthropic 内容块必须是对象","protocol_conversion")
            kind=item.get("type")
            if kind=="text":parts.append({"type":"text","text":item.get("text","")})
            elif kind=="thinking":parts.append({"type":"reasoning","text":item.get("thinking","")})
            elif kind=="image":
                source=item.get("source") or {};source_type=source.get("type")
                if source_type=="base64" and source.get("data"):
                    media_type=source.get("media_type") or "image/jpeg"
                    parts.append({"type":"image","image_url":{"url":f"data:{media_type};base64,{source['data']}"}})
                elif source_type=="url" and source.get("url"):
                    parts.append({"type":"image","image_url":{"url":source["url"]}})
                else:raise ProtocolError("protocol_conversion_unsupported","Anthropic 图像来源无法可靠转换","protocol_conversion")
            elif kind=="document":
                source=item.get("source") or {};source_type=source.get("type")
                if source_type=="base64" and source.get("data"):
                    media_type=source.get("media_type") or "application/octet-stream"
                    parts.append({"type":"file","file":{"type":"input_file","file_data":f"data:{media_type};base64,{source['data']}"}})
                elif source_type=="url" and source.get("url"):
                    parts.append({"type":"file","file":{"type":"input_file","file_url":source["url"]}})
                else:raise ProtocolError("protocol_conversion_unsupported","Anthropic 文档来源无法可靠转换","protocol_conversion")
            elif kind=="tool_use":parts.append({"type":"tool_call","id":item.get("id"),"name":item.get("name"),"arguments":item.get("input") or {}})
            elif kind=="tool_result":parts.append({"type":"tool_result","tool_call_id":item.get("tool_use_id"),"content":item.get("content","")})
            else:raise ProtocolError("protocol_conversion_unsupported",f"Anthropic {kind or 'unknown'} 内容无法可靠跨协议转换","protocol_conversion")
        return parts
    if request.inbound_protocol=="gemini_v1beta":
        parts=[];content=message.get("content",[]);content=[{"text":content}] if isinstance(content,str) else content
        for item in content:
            if not isinstance(item,dict):raise ProtocolError("protocol_conversion_unsupported","Gemini part 必须是对象","protocol_conversion")
            if "text" in item and item.get("thought"):parts.append({"type":"reasoning","text":item.get("text","")})
            elif "text" in item:parts.append({"type":"text","text":item.get("text","")})
            elif isinstance(item.get("functionCall"),dict):
                call=item["functionCall"];parts.append({"type":"tool_call","id":None,"name":call.get("name"),"arguments":call.get("args") or {}})
            elif isinstance(item.get("functionResponse"),dict):
                result=item["functionResponse"];parts.append({"type":"tool_result","tool_call_id":result.get("name"),"name":result.get("name"),"content":result.get("response") or {}})
            elif isinstance(item.get("inlineData") or item.get("inline_data"),dict):
                media=item.get("inlineData") or item.get("inline_data") or {};mime=str(media.get("mimeType") or media.get("mime_type") or "application/octet-stream");data=media.get("data")
                if not data:raise ProtocolError("protocol_conversion_unsupported","Gemini inlineData 缺少数据","protocol_conversion")
                if mime.startswith("image/"):parts.append({"type":"image","image_url":{"url":f"data:{mime};base64,{data}"}})
                elif mime.startswith("audio/"):parts.append({"type":"audio","audio":{"data":data,"format":mime.split("/",1)[-1]}})
                else:parts.append({"type":"file","file":{"type":"input_file","file_data":f"data:{mime};base64,{data}"}})
            elif isinstance(item.get("fileData") or item.get("file_data"),dict):
                media=item.get("fileData") or item.get("file_data") or {};uri=media.get("fileUri") or media.get("file_uri")
                if not uri:raise ProtocolError("protocol_conversion_unsupported","Gemini fileData 缺少 URI","protocol_conversion")
                parts.append({"type":"file","file":{"type":"input_file","file_url":uri}})
            else:raise ProtocolError("protocol_conversion_unsupported","Gemini 多媒体 part 无法可靠跨协议转换","protocol_conversion")
        return parts
    raise ProtocolError("protocol_conversion_unsupported","未知入口消息格式","protocol_conversion")


def _messages_for_openai(request:CanonicalRequest)->list[dict[str,Any]]:
    if request.inbound_protocol=="openai_chat":return list(request.messages)
    output=[];emitted_call_ids:set[str]=set();pending_call_ids:dict[str,list[str]]={}
    for message in request.messages:
        if not isinstance(message,dict):raise ProtocolError("protocol_conversion_unsupported","消息必须是对象","protocol_conversion")
        role="assistant" if message.get("role") in {"assistant","model"} else ("system" if message.get("role")=="system" else "user")
        parts=_canonical_message_parts(request,message);texts=[str(item.get("text","")) for item in parts if item["type"]=="text"];reasoning=[str(item.get("text","")) for item in parts if item["type"]=="reasoning"]
        media=[item for item in parts if item["type"] in {"image","file","audio"}]
        calls=[item for item in parts if item["type"]=="tool_call"];results=[item for item in parts if item["type"]=="tool_result"]
        if texts or calls or reasoning or media:
            content_value:Any="\n".join(texts) or None
            if media:
                content_value=[*([{"type":"text","text":"\n".join(texts)}] if texts else [])]
                for part in media:
                    if part["type"]=="image":content_value.append({"type":"image_url","image_url":part.get("image_url")})
                    elif part["type"]=="file":content_value.append(part.get("file") or {})
                    else:content_value.append({"type":"input_audio","input_audio":part.get("audio")})
            item={"role":role,"content":content_value}
            if reasoning:item["reasoning_content"]="\n".join(reasoning)
            if calls:
                tool_calls=[]
                for index,call in enumerate(calls):
                    call_id=str(call.get("id") or f"call_{len(output)}_{index}");name=str(call.get("name") or "")
                    emitted_call_ids.add(call_id);pending_call_ids.setdefault(name,[]).append(call_id)
                    tool_calls.append({"id":call_id,"type":"function","function":{"name":name,"arguments":__import__("json").dumps(call.get("arguments") or {},ensure_ascii=False,separators=(",",":"))}})
                item["tool_calls"]=tool_calls
            output.append(item)
        for result in results:
            content=result.get("content","") if isinstance(result.get("content"),str) else __import__("json").dumps(result.get("content") or {},ensure_ascii=False)
            raw_id=str(result.get("tool_call_id") or "");name=str(result.get("name") or "")
            call_id=raw_id if raw_id in emitted_call_ids else ""
            if not call_id and name and pending_call_ids.get(name):call_id=pending_call_ids[name].pop(0)
            if not call_id and raw_id and pending_call_ids.get(raw_id):call_id=pending_call_ids[raw_id].pop(0)
            if call_id:output.append({"role":"tool","tool_call_id":call_id,"content":content})
            else:
                # Responses API may send only function_call_output together
                # with previous_response_id.  Chat Completions has no server-
                # side conversation state, so an orphan tool message would be
                # rejected with HTTP 400. Preserve the result as user text.
                label=name or raw_id or "unknown"
                output.append({"role":"user","content":f"Tool result ({label}): {content}"})
    return output


def _upstream_http_error_details(response:httpx.Response,provider_id:int)->dict[str,Any]:
    details:dict[str,Any]={"provider_instance_id":provider_id,"status_code":response.status_code}
    try:payload=response.json()
    except ValueError:return details
    error=payload.get("error") if isinstance(payload,dict) else None
    if isinstance(error,dict):
        message=error.get("message") or error.get("detail")
        code=error.get("code") or error.get("type")
    else:
        message=error if isinstance(error,str) else (payload.get("message") if isinstance(payload,dict) else None)
        code=payload.get("code") if isinstance(payload,dict) else None
    if message:details["upstream_error_message"]=str(message)[:500]
    if code:details["upstream_error_code"]=str(code)[:128]
    return details


def _split_data_uri(value:Any)->tuple[str,str]|None:
    if not isinstance(value,str):return None
    matched=re.fullmatch(r"data:([^;,]+);base64,(.+)",value,flags=re.DOTALL)
    return (matched.group(1),matched.group(2)) if matched else None


def _canonical_media_url(part:dict[str,Any])->str:
    value=part.get("image_url") or part.get("url")
    if isinstance(value,dict):value=value.get("url")
    return str(value or "")


def _messages_for_anthropic(request:CanonicalRequest)->list[dict[str,Any]]:
    if request.inbound_protocol=="anthropic_messages":
        output=[]
        for message in request.messages:
            if not isinstance(message,dict) or message.get("role")=="system":continue
            item=dict(message);content=item.get("content")
            if isinstance(content,list):
                blocks=[]
                for block in content:
                    if isinstance(block,dict) and block.get("type")=="thinking" and str(block.get("signature") or "").startswith("apiswitch_v1_"):
                        blocks.append({"type":"text","text":f"<thinking>\n{block.get('thinking','')}\n</thinking>"})
                    else:blocks.append(block)
                item["content"]=blocks
            output.append(item)
        return output
    output=[]
    for message in request.messages:
        if not isinstance(message,dict) or message.get("role")=="system":continue
        role="assistant" if message.get("role") in {"assistant","model"} else "user";blocks=[]
        for part in _canonical_message_parts(request,message):
            if part["type"]=="text":blocks.append({"type":"text","text":part.get("text","")})
            elif part["type"]=="reasoning":blocks.append({"type":"thinking","thinking":part.get("text","")})
            elif part["type"]=="image":
                url=_canonical_media_url(part);inline=_split_data_uri(url)
                if inline:blocks.append({"type":"image","source":{"type":"base64","media_type":inline[0],"data":inline[1]}})
                elif url:blocks.append({"type":"image","source":{"type":"url","url":url}})
                else:raise ProtocolError("protocol_conversion_unsupported","图像缺少可转换的数据或 URL","protocol_conversion")
            elif part["type"]=="file":
                file=part.get("file") or {};file_data=file.get("file_data");file_url=file.get("file_url");inline=_split_data_uri(file_data)
                if inline:blocks.append({"type":"document","source":{"type":"base64","media_type":inline[0],"data":inline[1]}})
                elif file_url:blocks.append({"type":"document","source":{"type":"url","url":file_url}})
                else:raise ProtocolError("protocol_conversion_unsupported","文件缺少可转换的数据或 URL","protocol_conversion")
            elif part["type"]=="audio":raise ProtocolError("protocol_conversion_unsupported","Anthropic Messages 无法可靠表达音频块","protocol_conversion")
            elif part["type"]=="tool_call":blocks.append({"type":"tool_use","id":part.get("id") or f"toolu_{len(output)}","name":part.get("name"),"input":part.get("arguments") or {}})
            elif part["type"]=="tool_result":blocks.append({"type":"tool_result","tool_use_id":part.get("tool_call_id") or part.get("name"),"content":part.get("content","")})
            else:raise ProtocolError("protocol_conversion_unsupported",f"Anthropic 无法表达 {part['type']} 内容","protocol_conversion")
        if blocks:output.append({"role":role,"content":blocks})
    return output


def _messages_for_gemini(request:CanonicalRequest)->list[dict[str,Any]]:
    if request.inbound_protocol=="gemini_v1beta":
        return [{"role":"model" if message.get("role") in {"assistant","model"} else "user","parts":[{"text":message.get("content","")}] if isinstance(message.get("content"),str) else message.get("content",[])} for message in request.messages if isinstance(message,dict) and message.get("role")!="system"]
    output=[];call_names:dict[str,str]={}
    for message in request.messages:
        if not isinstance(message,dict) or message.get("role")=="system":continue
        role="model" if message.get("role") in {"assistant","model"} else "user";parts=[]
        for part in _canonical_message_parts(request,message):
            if part["type"]=="text":parts.append({"text":part.get("text","")})
            elif part["type"]=="reasoning":parts.append({"text":part.get("text","") ,"thought":True})
            elif part["type"]=="image":
                url=_canonical_media_url(part);inline=_split_data_uri(url)
                if inline:parts.append({"inlineData":{"mimeType":inline[0],"data":inline[1]}})
                elif url:parts.append({"fileData":{"mimeType":"image/*","fileUri":url}})
                else:raise ProtocolError("protocol_conversion_unsupported","图像缺少可转换的数据或 URL","protocol_conversion")
            elif part["type"]=="file":
                file=part.get("file") or {};inline=_split_data_uri(file.get("file_data"));file_url=file.get("file_url")
                if inline:parts.append({"inlineData":{"mimeType":inline[0],"data":inline[1]}})
                elif file_url:parts.append({"fileData":{"mimeType":"application/octet-stream","fileUri":file_url}})
                else:raise ProtocolError("protocol_conversion_unsupported","文件缺少可转换的数据或 URL","protocol_conversion")
            elif part["type"]=="audio":
                audio=part.get("audio") or {};data=audio.get("data");audio_format=str(audio.get("format") or "wav")
                if not data:raise ProtocolError("protocol_conversion_unsupported","音频缺少可转换的数据","protocol_conversion")
                parts.append({"inlineData":{"mimeType":f"audio/{audio_format}","data":data}})
            elif part["type"]=="tool_call":
                name=str(part.get("name") or "");parts.append({"functionCall":{"name":name,"args":part.get("arguments") or {}}})
                if part.get("id"):call_names[str(part["id"])]=name
            elif part["type"]=="tool_result":
                name=str(part.get("name") or call_names.get(str(part.get("tool_call_id")),""))
                if not name:raise ProtocolError("protocol_conversion_unsupported","工具结果缺少可映射的函数名","protocol_conversion")
                content=part.get("content");response=content if isinstance(content,dict) else {"result":content}
                parts.append({"functionResponse":{"name":name,"response":response}})
            else:raise ProtocolError("protocol_conversion_unsupported",f"Gemini 无法表达 {part['type']} 内容","protocol_conversion")
        if parts:output.append({"role":role,"parts":parts})
    return output


def _system_text(request:CanonicalRequest)->str:
    values=[]
    if isinstance(request.instructions,str):values.append(request.instructions)
    elif isinstance(request.instructions,list):
        for index,part in enumerate(request.instructions):
            if not isinstance(part,dict) or part.get("type")!="text" or not isinstance(part.get("text"),str):
                raise ProtocolError("protocol_conversion_unsupported",f"system[{index}] 不是可转换的文本块","protocol_conversion")
            values.append(part["text"])
    elif request.instructions is not None:
        raise ProtocolError("protocol_conversion_unsupported","system 必须是字符串或文本块数组","protocol_conversion")
    for message in request.messages:
        if not isinstance(message,dict) or message.get("role")!="system":continue
        for part in _canonical_message_parts(request,message):
            if part["type"]!="text":raise ProtocolError("protocol_conversion_unsupported","系统消息只支持文本跨协议转换","protocol_conversion")
            values.append(str(part.get("text","")))
    return "\n".join(value for value in values if value)


def provider_headers(provider: ProviderInstance) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    try:
        api_key = secret_crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
        custom = {key: secret_crypto.decrypt(value) for key, value in (provider.custom_headers_encrypted_json or {}).items()}
    except SecretCryptoError as exc:
        raise ProtocolError("credential_decryption_failed", str(exc), "upstream_credentials") from exc
    if provider.protocol_type in {"openai", "openai_compatible"} and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider.protocol_type == "anthropic_messages" and api_key:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    headers.update(custom)
    return headers


def _openai_endpoint_url(provider: ProviderInstance, base: str, endpoint_path: str) -> str:
    """Build an OpenAI-compatible endpoint using the catalog path as a hint.

    Manual/custom templates can declare ``/v1/models`` while the saved Base URL
    contains only the origin.  In that configuration discovery previously used
    ``/v1/models`` but inference incorrectly used ``/chat/completions``.  Reuse
    the model-catalog prefix for every OpenAI-compatible endpoint, while avoiding
    a duplicated prefix when the Base URL already ends in it.
    """
    template = get_template(provider.template_key) or {}
    model_list_path = str(template.get("model_list_path") or "/models")
    api_prefix = model_list_path[:-len("/models")] if model_list_path.endswith("/models") else ""
    base_path = urlsplit(base).path.rstrip("/")
    if api_prefix and not (base_path == api_prefix or base_path.endswith(api_prefix)):
        return base + api_prefix + endpoint_path
    return base + endpoint_path


async def discover_models(provider: ProviderInstance) -> list[dict[str, Any]]:
    """Fetch and normalize a provider model catalog without exposing secrets."""
    if provider.base_url.startswith("mock://"):
        return []
    try:base=validate_outbound_url(provider.base_url,"供应商 Base URL")
    except OutboundURLRejected as exc:raise ProtocolError("invalid_provider_url",str(exc),"provider_test") from exc
    headers=provider_headers(provider);protocol=provider.protocol_type
    template=get_template(provider.template_key) or {}
    model_list_path=template.get("model_list_path")
    if model_list_path == "":
        raise ProtocolError("model_discovery_unsupported","该供应商没有可可靠调用的模型目录，请手工添加上游模型","provider_test",{"template_key":provider.template_key})
    if protocol in {"openai","openai_compatible"}:
        path=str(model_list_path or "/models")
        url=_openai_endpoint_url(provider,base,"/models") if path.endswith("/models") else base+path
    elif protocol=="anthropic_messages":
        url=base+str(model_list_path or ("/models" if base.endswith("/v1") else "/v1/models"))
    elif protocol=="gemini":
        key=secret_crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
        url=base+"/v1beta/models"+(f"?key={quote(key,safe='')}" if key else "")
    elif protocol=="custom":
        raise ProtocolError("model_discovery_unsupported","自定义协议未配置模型目录适配器，请手工添加上游模型","provider_test",{"template_key":provider.template_key})
    else:
        raise ProtocolError("protocol_conversion_unsupported",f"未知供应商协议：{protocol}","provider_test")
    try:
        proxy=secret_crypto.decrypt(provider.proxy_url_encrypted) if getattr(provider,"proxy_url_encrypted",None) else None
        async with httpx.AsyncClient(timeout=provider.timeout_seconds,transport=HTTP_TRANSPORT,proxy=proxy) as client:
            response=await client.get(url,headers=headers)
    except httpx.TimeoutException as exc:raise ProtocolError("provider_timeout","供应商连接测试超时","provider_test") from exc
    except httpx.HTTPError as exc:raise ProtocolError("provider_unavailable","无法连接供应商","provider_test") from exc
    if response.status_code>=400:raise ProtocolError("upstream_http_error",f"供应商返回 HTTP {response.status_code}","provider_test",{"status_code":response.status_code})
    try:payload=response.json()
    except ValueError as exc:raise ProtocolError("invalid_upstream_response","模型目录不是有效 JSON","provider_test") from exc
    raw=payload.get("models",[]) if protocol=="gemini" else payload.get("data",payload if isinstance(payload,list) else [])
    if not isinstance(raw,list):raise ProtocolError("invalid_upstream_response","模型目录不是数组","provider_test")
    models=[]
    for item in raw:
        if not isinstance(item,dict):continue
        raw_model_id=str(item.get("id") or item.get("name") or "").strip()
        # OpenAI-compatible catalogs may use namespaced IDs such as
        # ``deepseek-ai/DeepSeek-V4-Flash``.  Those IDs are opaque and must be
        # sent back verbatim.  Gemini is the exception: its list API returns
        # resource names with the protocol-owned ``models/`` prefix.
        model_id=raw_model_id.removeprefix("models/") if protocol=="gemini" else raw_model_id
        if model_id:
            inferred=infer_model_characteristics(model_id,item)
            inferred={key:value for key,value in inferred.items() if value is not None}
            models.append({"model_id":model_id,"display_name":item.get("display_name") or item.get("displayName") or model_id,**inferred,"remote_metadata":item})
    return models


def _openai_payload(request: CanonicalRequest, model: str) -> dict[str, Any]:
    if request.request_type == "chat":
        if request.parameters.get("top_k") is not None:
            raise ProtocolError("protocol_conversion_unsupported","OpenAI-Compatible 协议无法可靠表达 top_k","upstream_conversion")
        parameters={key:value for key,value in request.parameters.items() if key!="top_k"}
        messages=_messages_for_openai(request)
        payload: dict[str, Any] = {"model": model, "messages": messages, **parameters}
        if request.instructions and not any(item.get("role") == "system" for item in messages if isinstance(item, dict)):
            system=_system_text(request)
            if system:payload["messages"] = [{"role": "system", "content": system}, *messages]
        if request.tools: payload["tools"] = _tools_for_provider(request,"openai")
        if request.tool_choice is not None:payload["tool_choice"]=_tool_choice_for_provider(request,"openai")
        # The gateway still emits the client-facing SSE itself, but compatible
        # providers may be more reliable in streaming mode. Their chunks are
        # collected into one canonical response below before egress rendering.
        payload["stream"] = request.stream
        if request.stream:payload["stream_options"]={"include_usage":True}
        return payload
    return {key: value for key, value in request.parameters.items() if not key.startswith("_apiswitch_")} | {"model": model}


def _anthropic_payload(request: CanonicalRequest, model: str) -> dict[str, Any]:
    if request.request_type != "chat":
        raise ProtocolError("protocol_conversion_unsupported", "Anthropic Messages 供应商不支持该终端能力", "upstream_conversion")
    messages = _messages_for_anthropic(request)
    unsupported=set(request.parameters)&{"frequency_penalty","presence_penalty","seed","response_format"}
    if unsupported:
        raise ProtocolError("protocol_conversion_unsupported","Anthropic Messages 无法可靠表达参数："+", ".join(sorted(unsupported)),"upstream_conversion")
    system = _system_text(request)
    payload: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": request.parameters.get("max_tokens") or 1024, "stream": False}
    for key in ("temperature","top_p","top_k","stop_sequences"):
        source="stop" if key=="stop_sequences" else key
        if request.parameters.get(source) is not None:payload[key]=request.parameters[source]
    if system: payload["system"] = system
    if request.tools: payload["tools"] = _tools_for_provider(request,"anthropic_messages")
    if request.tool_choice is not None:payload["tool_choice"]=_tool_choice_for_provider(request,"anthropic_messages")
    return payload


def _gemini_payload(request: CanonicalRequest) -> dict[str, Any]:
    if request.request_type != "chat":
        raise ProtocolError("protocol_conversion_unsupported", "Gemini 供应商不支持该终端能力转换", "upstream_conversion")
    contents=_messages_for_gemini(request);system=_system_text(request);system_parts=[{"text":system}] if system else []
    payload:dict[str,Any]={"contents":contents or [{"role":"user","parts":[{"text":""}]}]}
    if system_parts: payload["systemInstruction"]={"parts":system_parts}
    if request.tools: payload["tools"]=_tools_for_provider(request,"gemini")
    if request.tool_choice is not None:payload["toolConfig"]=_tool_choice_for_provider(request,"gemini")
    generation={}
    for source,target in (("temperature","temperature"),("top_p","topP"),("top_k","topK"),("max_tokens","maxOutputTokens"),("stop","stopSequences"),("frequency_penalty","frequencyPenalty"),("presence_penalty","presencePenalty"),("seed","seed")):
        if request.parameters.get(source) is not None:generation[target]=request.parameters[source]
    response_format=request.parameters.get("response_format")
    if isinstance(response_format,dict):
        format_type=response_format.get("type")
        if format_type=="json_object":generation["responseMimeType"]="application/json"
        elif format_type=="json_schema":
            generation["responseMimeType"]="application/json"
            schema=response_format.get("json_schema") or {}
            generation["responseSchema"]=schema.get("schema",schema)
        else:raise ProtocolError("protocol_conversion_unsupported",f"Gemini 无法可靠表达 response_format.type={format_type}","upstream_conversion")
    if generation:payload["generationConfig"]=generation
    return payload


def _openai_path(request_type: str, operation: str | None = None) -> str:
    operation_paths = {
        "images_generations": "/images/generations",
        "images_edits": "/images/edits",
        "images_variations": "/images/variations",
        "audio_speech": "/audio/speech",
        "audio_transcriptions": "/audio/transcriptions",
    }
    if operation in operation_paths:
        return operation_paths[operation]
    paths={"chat":"/chat/completions","embeddings":"/embeddings","images":"/images/generations","audio":"/audio/speech","moderations":"/moderations","rerank":"/rerank","search":"/search","batches":"/batches","video":"/videos/generations","music":"/music/generations"}
    if request_type not in paths:raise ProtocolError("protocol_conversion_unsupported",f"OpenAI-Compatible 未定义 {request_type} 上游端点","upstream_conversion")
    return paths[request_type]


def _tool_arguments(value:Any)->Any:
    import json
    if not isinstance(value,str):return value or {}
    try:return json.loads(value)
    except ValueError:return value


def _upstream_error(raw:Any)->tuple[str,dict[str,Any]]|None:
    """Recognize common JSON error envelopes, including ModelScope's plural form."""
    if not isinstance(raw,dict):return None
    for key in ("error","errors"):
        if not raw.get(key):continue
        error=raw[key]
        if isinstance(error,dict):message=str(error.get("message") or error.get("detail") or error.get("type") or "未知错误")
        elif isinstance(error,list):
            messages=[str(item.get("message") or item.get("detail") or item) if isinstance(item,dict) else str(item) for item in error[:5]]
            message="; ".join(messages) or "未知错误"
        else:message=str(error)
        return message[:500],{"error_envelope":key}
    code=raw.get("Code",raw.get("code"))
    if code not in (None,0,200,"0","200","ok","OK","success","SUCCESS"):
        message=str(raw.get("Message") or raw.get("message") or raw.get("detail") or "未知错误")
        return message[:500],{"upstream_code":str(code)[:100]}
    if raw.get("success") is False:
        message=str(raw.get("message") or raw.get("detail") or "上游报告请求失败")
        return message[:500],{"upstream_success":False}
    return None


def _response_shape(value:Any,depth:int=0)->Any:
    """Return keys and container types only; never include upstream content or secrets."""
    if depth>=5:return type(value).__name__
    if isinstance(value,dict):return {str(key):_response_shape(item,depth+1) for key,item in list(value.items())[:20]}
    if isinstance(value,list):return [_response_shape(value[0],depth+1)] if value else []
    return type(value).__name__


def _retryable_empty_openai_response(raw:Any,protocol:str,request_type:str)->bool:
    """Retry when a compatible backend produced no completion output.

    Some OpenAI-compatible inference services account prompt tokens and return a
    transient ``choices: null`` placeholder with zero completion tokens.  It is
    safe to retry that response because there is no model output to lose.  Never
    retry when the provider reports generated output tokens.
    """
    if protocol not in {"openai","openai_compatible"} or request_type!="chat":return False
    if isinstance(raw,list):
        events=[item for item in raw if isinstance(item,dict)]
        if any(isinstance(item.get("choices"),list) and item["choices"] for item in events):return False
        usage=next((item["usage"] for item in reversed(events) if isinstance(item.get("usage"),dict)),{})
        raw={"choices":[],"usage":usage}
    if not isinstance(raw,dict):return False
    if raw.get("choices") not in (None,[]):return False
    usage=raw.get("usage")
    if not isinstance(usage,dict):return False
    completion=usage.get("completion_tokens",usage.get("output_tokens"))
    if completion is not None:return completion in (0,0.0,"0")
    prompt=usage.get("prompt_tokens",usage.get("input_tokens"));total=usage.get("total_tokens")
    return prompt is not None and total is not None and str(prompt)==str(total)


def _openai_sse_events(body:str)->list[dict[str,Any]]:
    events=[]
    for line in body.splitlines():
        if not line.startswith("data:"):continue
        data=line[len("data:"):].strip()
        if not data or data=="[DONE]":continue
        value=json.loads(data)
        if not isinstance(value,dict):raise ValueError("SSE data is not an object")
        events.append(value)
    if not events:raise ValueError("SSE contains no JSON data events")
    return events


def _openai_text_content(value:Any,path:str)->str:
    if value is None:return ""
    if isinstance(value,str):return value
    parts=value if isinstance(value,list) else [value]
    text=[]
    for index,part in enumerate(parts):
        if isinstance(part,str):text.append(part);continue
        if not isinstance(part,dict):raise KeyError(f"{path}[{index}] is not a text part")
        part_type=part.get("type")
        part_text=part.get("text")
        if part_type not in {None,"text","output_text"} or not isinstance(part_text,str):
            raise KeyError(f"{path}[{index}] is not a supported text part")
        text.append(part_text)
    return "".join(text)


def _openai_message_content(value:Any,path:str)->tuple[str,str]:
    """Split typed text/reasoning parts without discarding unknown content."""
    if not isinstance(value,list):return _openai_text_content(value,path),""
    text:list[str]=[];reasoning:list[str]=[]
    for index,part in enumerate(value):
        if isinstance(part,str):text.append(part);continue
        if not isinstance(part,dict):raise KeyError(f"{path}[{index}] is not a text part")
        part_type=str(part.get("type") or "text").lower()
        part_text=part.get("text")
        if not isinstance(part_text,str):raise KeyError(f"{path}[{index}] has no text")
        if part_type in {"text","output_text"}:text.append(part_text)
        elif part_type in {"reasoning","reasoning_text","thinking"}:reasoning.append(part_text)
        else:raise KeyError(f"{path}[{index}] is not a supported text part")
    return "".join(text),"".join(reasoning)


def _openai_response_payload(raw:Any,request:CanonicalRequest)->dict[str,Any]:
    """Normalize compatible response envelopes and completed JSON chunk arrays."""
    def walk(value:Any,depth:int=0)->dict[str,Any]|None:
        if depth>3 or not isinstance(value,dict):return None
        if isinstance(value.get("choices"),list):return value
        direct=value.get("generated_text",value.get("output_text"))
        if isinstance(direct,str) and not request.tools:return {"choices":[{"text":direct,"finish_reason":"stop"}],"usage":value.get("usage") or {}}
        for key in ("output","data","result","response"):
            nested=value.get(key)
            if isinstance(nested,dict):
                found=walk(nested,depth+1)
                if found:
                    if not found.get("usage") and isinstance(value.get("usage"),dict):found={**found,"usage":value["usage"]}
                    return found
                direct=nested.get("generated_text",nested.get("output_text",nested.get("text")))
                if isinstance(direct,str) and not request.tools:return {"choices":[{"text":direct,"finish_reason":"stop"}],"usage":value.get("usage") or nested.get("usage") or {}}
            elif isinstance(nested,str) and not request.tools:return {"choices":[{"text":nested,"finish_reason":"stop"}],"usage":value.get("usage") or {}}
        return None

    found=walk(raw)
    if found:return found
    if isinstance(raw,list) and raw:
        text_parts:list[str]=[];reasoning_parts:list[str]=[];usage:dict[str,Any]={};finish_reason:Any=None
        tool_fragments:dict[int,dict[str,Any]]={};saw_choice=False
        for event in raw:
            payload=walk(event)
            if not payload:raise KeyError("chunk array contains an unknown event")
            if isinstance(payload.get("usage"),dict):usage.update(payload["usage"])
            if not payload.get("choices"):continue
            choice=payload["choices"][0]
            if not isinstance(choice,dict):raise KeyError("chunk choice is not an object")
            saw_choice=True
            delta=choice.get("delta")
            if not isinstance(delta,dict):raise KeyError("chunk has no delta")
            text,part_reasoning=_openai_message_content(delta.get("content"),"choices[0].delta.content")
            text_parts.append(text);reasoning_parts.append(_openai_text_content(delta.get("reasoning_content"),"choices[0].delta.reasoning_content") or part_reasoning)
            for position,item in enumerate(delta.get("tool_calls") or []):
                if not isinstance(item,dict):raise KeyError("tool call delta is not an object")
                index=item.get("index",position)
                if not isinstance(index,int):raise KeyError("tool call delta index is not an integer")
                fragment=tool_fragments.setdefault(index,{"id":None,"type":"function","function":{"name":"","arguments":""}})
                if item.get("id"):fragment["id"]=item["id"]
                if item.get("type"):fragment["type"]=item["type"]
                function=item.get("function") or {}
                if not isinstance(function,dict):raise KeyError("tool call delta function is not an object")
                if function.get("name"):fragment["function"]["name"]+=str(function["name"])
                if function.get("arguments"):fragment["function"]["arguments"]+=str(function["arguments"])
            if choice.get("finish_reason") is not None:finish_reason=choice["finish_reason"]
        if not saw_choice or finish_reason is None:raise KeyError("chunk array is unfinished")
        message={"content":"".join(text_parts),"reasoning_content":"".join(reasoning_parts)}
        if tool_fragments:message["tool_calls"]=[tool_fragments[index] for index in sorted(tool_fragments)]
        return {"choices":[{"message":message,"finish_reason":finish_reason}],"usage":usage}
    if isinstance(raw,dict):return raw
    raise KeyError("response is not an object")


def _openai_tool_results(container:dict[str,Any])->list[dict[str,Any]]:
    items=container.get("tool_calls") or []
    if not isinstance(items,list):raise KeyError("tool_calls is not a list or null")
    result=[{"id":item.get("id"),"name":(item.get("function") or {}).get("name",""),"arguments":_tool_arguments((item.get("function") or {}).get("arguments",{}))} for item in items if isinstance(item,dict)]
    legacy=container.get("function_calls") or container.get("function_call") or []
    if isinstance(legacy,dict):legacy=[legacy]
    if not isinstance(legacy,list):raise KeyError("function_calls is not a list, object or null")
    result.extend({"id":item.get("id"),"name":item.get("name","") or (item.get("function") or {}).get("name",""),"arguments":_tool_arguments(item.get("arguments",{}) if "arguments" in item else (item.get("function") or {}).get("arguments",{}))} for item in legacy if isinstance(item,dict))
    return result


def _openai_choice(choice:Any,request:CanonicalRequest,object_type:str)->tuple[str,str,list[dict[str,Any]]]:
    if not isinstance(choice,dict):raise KeyError("choices[0] is not an object")
    message=choice.get("message")
    if isinstance(message,dict):
        text,part_reasoning=_openai_message_content(message.get("content"),"choices[0].message.content")
        reasoning=_openai_text_content(message.get("reasoning_content"),"choices[0].message.reasoning_content") or part_reasoning
        return text,reasoning,_openai_tool_results(message)
    if isinstance(message,str) and not request.tools:return message,"",[]
    if isinstance(choice.get("text"),str) and not request.tools:return choice["text"],"",[]
    if isinstance(choice.get("content"),str) and not request.tools:return choice["content"],"",[]
    delta=choice.get("delta")
    # A few compatible gateways return one completed chunk as JSON even when
    # stream=false. Accept it only when the chunk is explicitly final; accepting
    # an unfinished delta would silently truncate the answer.
    if isinstance(delta,dict) and choice.get("finish_reason") is not None:
        content=_openai_text_content(delta.get("content"),"choices[0].delta.content")
        reasoning=_openai_text_content(delta.get("reasoning_content"),"choices[0].delta.reasoning_content")
        return content,reasoning,_openai_tool_results(delta)
    raise KeyError("choices[0] has no lossless chat representation")


async def _call_http(candidate: RouteCandidate, request: CanonicalRequest) -> CanonicalResponse:
    provider=candidate.provider; model=candidate.upstream.model_id; protocol=provider.protocol_type
    if provider.base_url.startswith("mock://"):
        return CanonicalResponse(text="Mock upstream response",mock=True)
    try:base=validate_outbound_url(provider.base_url,"供应商 Base URL")
    except OutboundURLRejected as exc:raise ProtocolError("invalid_provider_url",str(exc),"upstream_configuration") from exc
    headers=provider_headers(provider)
    try:proxy=secret_crypto.decrypt(provider.proxy_url_encrypted) if getattr(provider,"proxy_url_encrypted",None) else None
    except SecretCryptoError as exc:raise ProtocolError("credential_decryption_failed",str(exc),"upstream_credentials") from exc
    if protocol in {"openai","openai_compatible"}:
        url=_openai_endpoint_url(provider,base,_openai_path(request.request_type, request.parameters.get("_apiswitch_operation"))); payload=_openai_payload(request,model)
        if provider.template_key == "sensenova" and request.request_type == "chat":
            # SenseNova compatible-mode v2 follows OpenAI's newer token field
            # and exposes slow-thinking through reasoning_effort.
            if payload.get("max_tokens") is not None:
                payload["max_completion_tokens"] = payload.pop("max_tokens")
    elif protocol=="anthropic_messages":
        url=base+("/messages" if base.endswith("/v1") else "/v1/messages");payload=_anthropic_payload(request,model)
    elif protocol=="gemini":
        try:key=secret_crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
        except SecretCryptoError as exc:raise ProtocolError("credential_decryption_failed",str(exc),"upstream_credentials") from exc
        suffix=f"/v1beta/models/{quote(model,safe='')}:generateContent";url=base+suffix+(f"?key={quote(key,safe='')}" if key else "");payload=_gemini_payload(request)
    else:
        raise ProtocolError("protocol_conversion_unsupported",f"自定义协议 {protocol} 尚未配置可靠转换器","upstream_conversion")
    raw:Any=None
    for attempt in range(EMPTY_COMPLETION_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=provider.timeout_seconds,transport=HTTP_TRANSPORT,proxy=proxy) as client:
                multipart=request.parameters.get("_apiswitch_multipart") or []
                if multipart:
                    headers.pop("Content-Type", None)
                    headers.pop("content-type", None)
                    files=[
                        (item["field"], (item["filename"], item["content"], item["content_type"]))
                        for item in multipart
                    ]
                    response=await client.post(url,headers=headers,data=payload,files=files)
                else:
                    response=await client.post(url,headers=headers,json=payload)
        except httpx.TimeoutException as exc:raise ProtocolError("provider_timeout","上游请求超时","upstream_call",{"provider_instance_id":provider.id}) from exc
        except httpx.HTTPError as exc:raise ProtocolError("provider_unavailable","无法连接上游供应商","upstream_call",{"provider_instance_id":provider.id}) from exc
        if response.status_code>=400:
            raise ProtocolError("upstream_http_error",f"上游返回 HTTP {response.status_code}","upstream_call",_upstream_http_error_details(response,provider.id))
        response_content_type=response.headers.get("content-type","").lower()
        is_audio_speech=request.parameters.get("_apiswitch_operation")=="audio_speech"
        if is_audio_speech and "json" not in response_content_type:
            if not response.content:
                raise ProtocolError("invalid_upstream_response","语音合成上游返回了空响应","upstream_response")
            return CanonicalResponse(
                binary=response.content,
                media_type=response.headers.get("content-type") or "application/octet-stream",
                mock=False,
                upstream_url=url.split("?",1)[0],
            )
        try:raw=_openai_sse_events(response.text) if "text/event-stream" in response_content_type else response.json()
        except ValueError as exc:raise ProtocolError("invalid_upstream_response","上游响应不是有效 JSON","upstream_response") from exc
        upstream_error=None
        if isinstance(raw,list):
            for event in raw:
                upstream_error=_upstream_error(event)
                if upstream_error:break
        else:upstream_error=_upstream_error(raw)
        if upstream_error:
            message,details=upstream_error
            raise ProtocolError("upstream_response_error",f"上游返回错误响应：{message}","upstream_response",{"provider_instance_id":provider.id,**details})
        if not _retryable_empty_openai_response(raw,protocol,request.request_type):break
        if attempt+1>=EMPTY_COMPLETION_MAX_ATTEMPTS:break
        if protocol in {"openai","openai_compatible"} and request.request_type=="chat":
            payload["stream"]=True;payload["stream_options"]={"include_usage":True};headers["Accept"]="text/event-stream"
        await asyncio.sleep(EMPTY_COMPLETION_RETRY_BASE_SECONDS*(2**attempt))
    text="";reasoning_content="";tool_calls=[]
    parsed_raw=raw
    if protocol in {"openai","openai_compatible"} and request.request_type=="chat":
        try:
            parsed_raw=_openai_response_payload(raw,request)
            text,reasoning_content,tool_calls=_openai_choice(parsed_raw["choices"][0],request,str(parsed_raw.get("object") or ""))
        except (KeyError,IndexError,TypeError) as exc:
            raise ProtocolError("invalid_upstream_response","OpenAI-Compatible 响应没有可无损转换的完整消息、文本或已结束增量","upstream_response",{"provider_instance_id":provider.id,"response_shape":_response_shape(raw)}) from exc
    elif protocol=="anthropic_messages":
        text="".join(str(part.get("text","")) for part in raw.get("content",[]) if isinstance(part,dict) and part.get("type")=="text")
        tool_calls=[{"id":part.get("id"),"name":part.get("name",""),"arguments":part.get("input") or {}} for part in raw.get("content",[]) if isinstance(part,dict) and part.get("type")=="tool_use"]
    elif protocol=="gemini":
        try:
            parts=raw["candidates"][0]["content"]["parts"];text="".join(str(part.get("text","")) for part in parts if isinstance(part,dict))
            tool_calls=[{"id":None,"name":part["functionCall"].get("name",""),"arguments":part["functionCall"].get("args") or {}} for part in parts if isinstance(part,dict) and isinstance(part.get("functionCall"),dict)]
        except (KeyError,IndexError,TypeError) as exc:raise ProtocolError("invalid_upstream_response","Gemini 响应缺少 candidates.content.parts","upstream_response") from exc
    usage=parsed_raw.get("usage",{}) if isinstance(parsed_raw,dict) else {}
    if not usage and isinstance(raw,dict):usage=raw.get("usage",{})
    return CanonicalResponse(text=text,reasoning_content=reasoning_content,tool_calls=tool_calls,raw=raw,usage=usage,mock=False,upstream_url=url.split("?",1)[0])


async def probe_model(provider: ProviderInstance, upstream: UpstreamModel) -> dict[str, Any]:
    """Run one intentionally tiny request to verify a discovered model's endpoint."""
    outputs = set(upstream.output_capabilities_json or [])
    request_type = next(
        (kind for capability, kind in (
            ("embeddings", "embeddings"), ("images", "images"), ("audio", "audio"),
            ("moderation", "moderations"), ("rerank", "rerank"), ("search", "search"),
            ("video", "video"), ("music", "music"),
        ) if capability in outputs),
        "chat",
    )
    if request_type == "chat":
        request = CanonicalRequest(
            "chat", "openai_chat", "probe", messages=[{"role": "user", "content": "hi"}],
            parameters={"max_tokens": 1}, required_input=["text"], required_output=["text"],
        )
    else:
        parameters: dict[str, Any] = {"input": "hi"}
        if request_type in {"images", "video", "music"}: parameters = {"prompt": "test"}
        elif request_type == "audio": parameters = {"input": "test", "voice": "alloy"}
        elif request_type == "rerank": parameters = {"query": "hi", "documents": ["hi"], "top_n": 1}
        elif request_type == "search": parameters = {"query": "hi", "max_results": 1}
        request = CanonicalRequest(request_type, request_type, "probe", parameters=parameters, required_output=list(outputs))
    candidate = RouteCandidate(SimpleNamespace(id=0, priority=0), upstream, provider, ["最小化检测"])
    response = await _call_http(candidate, request)
    return {
        "ok": True,
        "request_type": request_type,
        "upstream_url": response.upstream_url,
        "usage": response.usage,
    }


def _record_auxiliary_log(
    db:Session,request:CanonicalRequest,step:dict[str,Any],*,parent_request_id:str,
    request_id:str,started:Any,provider:ProviderInstance,upstream:UpstreamModel,
    api_token_id:int|None,token_prefix_snapshot:str|None,result:CanonicalResponse|None=None,
    error:ProtocolError|None=None,
)->None:
    latency_ms=(time.perf_counter()-step.pop("_clock"))*1000
    usage=(result.get("usage") or {}) if result is not None else {}
    input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    cost=(input_tokens*(upstream.input_price or 0)+output_tokens*(upstream.output_price or 0))/1_000_000
    step.update({"request_id":request_id,"parent_request_id":parent_request_id,"latency_ms":latency_ms,"input_tokens":input_tokens,"output_tokens":output_tokens,"estimated_cost":cost})
    summary={key:step.get(key) for key in ("workflow_id","workflow_type","step_index","attempt_index","input","output","status","parent_request_id","cache_status","shared_request_id")}
    db.add(RequestLog(
        request_id=request_id,request_kind="auxiliary",parent_request_id=parent_request_id,
        started_at=started,finished_at=utc_now(),inbound_protocol="auxiliary",
        unified_model=request.unified_model,provider_instance_id=provider.id,upstream_model_id=upstream.id,
        auxiliary_summary_json=summary,api_token_id=api_token_id,api_token_prefix_snapshot=token_prefix_snapshot,
        input_tokens=input_tokens,output_tokens=output_tokens,estimated_cost=cost,latency_ms=latency_ms,
        first_token_latency_ms=latency_ms,success=error is None,error_type=error.error_type if error else None,
        error_message=str(error) if error else None,failure_stage=error.stage if error else None,
    ))
    if error is None:
        db.add(UsageHistory(
            request_id=request_id,api_token_id=api_token_id,provider_instance_id=provider.id,
            upstream_model_id=upstream.id,unified_model=request.unified_model,inbound_protocol="auxiliary",
            input_tokens=input_tokens,output_tokens=output_tokens,estimated_cost=cost,
        ))


def _auxiliary_fingerprint(candidate:RouteCandidate,request:CanonicalRequest)->str:
    protocol=candidate.provider.protocol_type
    if protocol in {"openai","openai_compatible"}:payload=_openai_payload(request,candidate.upstream.model_id)
    elif protocol=="anthropic_messages":payload=_anthropic_payload(request,candidate.upstream.model_id)
    elif protocol=="gemini":payload=_gemini_payload(request)
    else:payload=request.dump()
    source={"provider_protocol":protocol,"upstream_model_id":candidate.upstream.id,"model":candidate.upstream.model_id,"request_type":request.request_type,"payload":payload}
    encoded=json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clone_auxiliary_response(result:CanonicalResponse,*,include_usage:bool)->CanonicalResponse:
    values=result.dump()
    if not include_usage:values["usage"]={}
    return CanonicalResponse(**values)


def _clear_auxiliary_runtime_state()->None:
    """Clear process-local auxiliary sharing state (used by isolation tests)."""
    with _auxiliary_runtime_lock:
        _auxiliary_cache.clear();_auxiliary_inflight.clear()


async def _call_auxiliary_shared(
    candidate:RouteCandidate,request:CanonicalRequest,*,source_request_id:str,require_text:bool,
)->tuple[CanonicalResponse,dict[str,str]]:
    """Coalesce identical helper calls and reuse only short-lived successes."""
    fingerprint=_auxiliary_fingerprint(candidate,request);now=time.monotonic();loop=asyncio.get_running_loop();inflight_key=(id(loop),fingerprint)
    with _auxiliary_runtime_lock:
        expired=[key for key,(expires,_,_) in _auxiliary_cache.items() if expires<=now]
        for key in expired:_auxiliary_cache.pop(key,None)
        cached=_auxiliary_cache.get(fingerprint)
        if cached:
            return _clone_auxiliary_response(cached[1],include_usage=False),{"cache_status":"hit","shared_request_id":cached[2]}
        shared=_auxiliary_inflight.get(inflight_key)
        if shared:
            task,shared_request_id=shared;cache_status="coalesced"
        else:
            async def invoke()->CanonicalResponse:
                response=await _call_http(candidate,request)
                if require_text and not _clean_auxiliary_text(str(response.get("text") or "")):
                    raise ProtocolError("empty_auxiliary_response","辅助模型没有返回可注入的文本结果","auxiliary_step")
                return response
            task=loop.create_task(invoke());shared_request_id=source_request_id;cache_status="miss"
            _auxiliary_inflight[inflight_key]=(task,shared_request_id)
    try:
        result=await asyncio.shield(task)
    except ProtocolError as exc:
        if cache_status=="miss":
            with _auxiliary_runtime_lock:
                current=_auxiliary_inflight.get(inflight_key)
                if current and current[0] is task:_auxiliary_inflight.pop(inflight_key,None)
        raise ProtocolError(exc.error_type,str(exc),exc.stage,{**exc.details,"auxiliary_cache_status":cache_status,"shared_request_id":shared_request_id}) from exc
    if cache_status=="miss":
        with _auxiliary_runtime_lock:
            current=_auxiliary_inflight.get(inflight_key)
            if current and current[0] is task:_auxiliary_inflight.pop(inflight_key,None)
            if len(_auxiliary_cache)>=AUXILIARY_CACHE_MAX_ENTRIES:
                oldest=min(_auxiliary_cache,key=lambda key:_auxiliary_cache[key][0]);_auxiliary_cache.pop(oldest,None)
            _auxiliary_cache[fingerprint]=(time.monotonic()+AUXILIARY_CACHE_TTL_SECONDS,_clone_auxiliary_response(result,include_usage=True),shared_request_id)
    return _clone_auxiliary_response(result,include_usage=cache_status=="miss"),{"cache_status":cache_status,"shared_request_id":shared_request_id}


async def _run_auxiliary_steps(
    db:Session,request:CanonicalRequest,plan:dict[str,Any],*,parent_request_id:str,
    api_token_id:int|None=None,token_prefix_snapshot:str|None=None,
    post_response:CanonicalResponse|None=None,
)->tuple[CanonicalRequest,CanonicalResponse|None]:
    terminal_response:CanonicalResponse|None=None
    for step in plan.get("steps",[]):
        is_post=step.get("workflow_type")=="structured_repair"
        if is_post != (post_response is not None):continue
        if step.get("workflow_type")=="terminal_capability":aux_request=request
        else:
            source_text=(post_response or {}).get("text")
            messages=list(request.messages)
            if source_text is not None:messages=[{"role":"user","content":f"请校验并修复以下输出，保持语义不变：\n{source_text}"}]
            workflow_type=str(step.get("workflow_type") or "")
            instructions=(
                "你是图像识别辅助模型。请围绕用户当前问题准确识别每张图片，先给出可直接支持回答的结论，"
                "再简短列出可见文字、界面状态或关键对象作为证据。不要猜测图片中不存在的内容，"
                "不要讨论你的推理过程，只返回可供文本模型作答的图像事实。"
                if workflow_type == "vision_to_text"
                else f"执行辅助工作流 {workflow_type}，只返回处理结果。"
            )
            aux_request=CanonicalRequest(
                "chat",request.inbound_protocol,request.unified_model,messages=messages,
                instructions=instructions,
                parameters={"temperature":0.1,"max_tokens":1200},
                required_input=[str(step.get("input","text"))],
                required_output=[str(step.get("output","text"))],
            )
        result:CanonicalResponse|None=None;result_text="";last_error:ProtocolError|None=None;attempts=[]
        candidate_specs=step.get("candidates") or [{key:step.get(key) for key in ("auxiliary_model_id","upstream_model_id","provider_instance_id","priority")}]
        for attempt_index,specification in enumerate(candidate_specs,1):
            upstream=db.get(UpstreamModel,specification["upstream_model_id"]);provider=db.get(ProviderInstance,specification["provider_instance_id"])
            if not upstream or not provider:
                last_error=ProtocolError("auxiliary_step_failed","辅助步骤引用已失效","auxiliary_step",{"upstream_model_id":specification.get("upstream_model_id")});attempts.append({"attempt_index":attempt_index,"status":"failed","cause":last_error.error_type});continue
            timeout=min(float(provider.timeout_seconds),float(step.get("timeout_seconds") or provider.timeout_seconds))
            provider_values={column.name:getattr(provider,column.name) for column in provider.__table__.columns};provider_values["timeout_seconds"]=timeout
            provider_for_step=SimpleNamespace(**provider_values)
            candidate=RouteCandidate(SimpleNamespace(id=specification.get("auxiliary_model_id"),priority=specification.get("priority",0)),upstream,provider_for_step,["辅助候选"])
            auxiliary_request_id=f"{parent_request_id}:aux:{step['workflow_id']}:{step['step_index']}:{attempt_index}:{uuid.uuid4().hex[:8]}"
            attempt_step={key:value for key,value in step.items() if key not in {"candidates","attempts","_clock"}}
            attempt_step.update(specification);attempt_step.update({"attempt_index":attempt_index,"_clock":time.perf_counter()});step_started=utc_now()
            try:
                result,sharing=await _call_auxiliary_shared(candidate,aux_request,source_request_id=auxiliary_request_id,require_text=step.get("workflow_type")!="terminal_capability")
                result_text=_clean_auxiliary_text(str(result.get("text") or ""));attempt_step.update(sharing);attempt_step["status"]="succeeded"
            except ProtocolError as exc:
                last_error=exc;attempt_step["status"]="failed";attempt_step["error_type"]=exc.error_type;attempt_step["cache_status"]=exc.details.get("auxiliary_cache_status","miss");attempt_step["shared_request_id"]=exc.details.get("shared_request_id",auxiliary_request_id)
                if attempt_step["cache_status"]=="miss":
                    _health(db,candidate,False,(time.perf_counter()-attempt_step["_clock"])*1000,str(exc),_trips_breaker(exc))
                    if exc.error_type=="upstream_http_error" and int(exc.details.get("status_code") or 0)==429:
                        db.flush();_open_breaker_immediately(db,candidate)
                _record_auxiliary_log(db,request,attempt_step,parent_request_id=parent_request_id,request_id=auxiliary_request_id,started=step_started,provider=provider,upstream=upstream,api_token_id=api_token_id,token_prefix_snapshot=token_prefix_snapshot,error=exc)
                attempts.append({"attempt_index":attempt_index,"auxiliary_model_id":specification.get("auxiliary_model_id"),"upstream_model_id":upstream.id,"provider_instance_id":provider.id,"status":"failed","cause":exc.error_type,"status_code":exc.details.get("status_code")})
                continue
            if attempt_step["cache_status"]=="miss":_health(db,candidate,True,(time.perf_counter()-attempt_step["_clock"])*1000)
            if result_text:attempt_step["output_chars"]=len(result_text)
            _record_auxiliary_log(db,request,attempt_step,parent_request_id=parent_request_id,request_id=auxiliary_request_id,started=step_started,provider=provider,upstream=upstream,api_token_id=api_token_id,token_prefix_snapshot=token_prefix_snapshot,result=result)
            attempts.append({"attempt_index":attempt_index,"auxiliary_model_id":specification.get("auxiliary_model_id"),"upstream_model_id":upstream.id,"provider_instance_id":provider.id,"status":"succeeded","cache_status":attempt_step["cache_status"]})
            step.update({key:specification.get(key) for key in ("auxiliary_model_id","upstream_model_id","provider_instance_id","priority")});step.update({"status":"succeeded","cache_status":attempt_step["cache_status"],"shared_request_id":attempt_step["shared_request_id"]});break
        step["attempts"]=attempts
        if result is None:
            step["status"]="failed";step["error_type"]=last_error.error_type if last_error else "provider_unavailable"
            details={"workflow_id":step["workflow_id"],"step_index":step["step_index"],"cause":step["error_type"],"attempts":attempts}
            if last_error:details.update({key:value for key,value in last_error.details.items() if key in {"status_code","upstream_error_code","upstream_error_message"}})
            raise ProtocolError("auxiliary_step_failed","全部辅助候选均执行失败","auxiliary_step",details) from last_error
        if step.get("workflow_type")=="terminal_capability":terminal_response=result
        elif is_post:post_response=result
        elif result_text:
            if step.get("workflow_type") == "vision_to_text":
                request.messages = _replace_vision_content(request.messages, result_text)
            else:
                request.messages=[*request.messages,{"role":"system","content":f"辅助工作流 {step.get('workflow_type')} 结果：\n{result_text}"}]
    return request,terminal_response or post_response


def _clean_auxiliary_text(text:str)->str:
    """Remove provider reasoning wrappers before injecting auxiliary output."""
    original=text.strip()
    if not original:return ""
    cleaned=re.sub(r"<(think|analysis)\b[^>]*>.*?</\1\s*>","",original,flags=re.IGNORECASE|re.DOTALL)
    cleaned=re.sub(r"<(think|analysis)\b[^>]*>.*\Z","",cleaned,flags=re.IGNORECASE|re.DOTALL)
    cleaned=re.sub(r"</?(think|analysis)\b[^>]*>","",cleaned,flags=re.IGNORECASE)
    return cleaned.strip()


def _replace_vision_content(messages:list[dict[str,Any]], description:str)->list[dict[str,Any]]:
    """Replace image parts from every supported ingress protocol."""
    replaced: list[dict[str,Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            replaced.append(message)
            continue
        parts: list[str] = [];preserved: list[Any] = []
        changed = False
        for part in content:
            if isinstance(part,dict):
                kind=part.get("type");inline=part.get("inlineData") or part.get("inline_data") or {};mime=str(inline.get("mimeType") or inline.get("mime_type") or "") if isinstance(inline,dict) else ""
                is_image=kind in {"image_url","input_image","image"} or bool(inline and mime.startswith("image/"))
                if is_image:changed=True;continue
                if kind in {"text","input_text","output_text"} or (kind is None and "text" in part):parts.append(str(part.get("text") or ""));continue
                preserved.append(part)
            elif isinstance(part, str):
                parts.append(part)
            else:preserved.append(part)
        if changed:
            text = "\n".join(item for item in parts if item.strip())
            if text:
                text += "\n"
            text += (
                "[APISwitch 图像辅助识别结果]\n"
                f"{description}\n"
                "[/APISwitch 图像辅助识别结果]\n"
                "请根据以上识别结果回答当前问题。"
            )
            updated = dict(message)
            if preserved:
                # Preserve unrelated audio/file/tool parts. Pick the text block
                # vocabulary already used by this message so no client-specific
                # branch is needed at the gateway boundary.
                if any(isinstance(item,dict) and ("inlineData" in item or "fileData" in item or "functionCall" in item) for item in content):text_part={"text":text}
                else:text_part={"type":"text","text":text}
                updated["content"]=[*preserved,text_part]
            else:updated["content"] = text
            replaced.append(updated)
        else:
            replaced.append(message)
    return replaced


def _circuit_breaker(db:Session,upstream_model_id:int)->CircuitBreaker:
    pending=next((row for row in db.new if isinstance(row,CircuitBreaker) and row.upstream_model_id==upstream_model_id),None)
    return pending or db.scalar(select(CircuitBreaker).where(CircuitBreaker.upstream_model_id==upstream_model_id)) or CircuitBreaker(upstream_model_id=upstream_model_id)


def _health(db:Session,candidate:RouteCandidate,success:bool,latency_ms:float,error:str|None=None,trip_breaker:bool=True)->None:
    row=db.scalar(select(ProviderHealth).where(ProviderHealth.upstream_model_id==candidate.upstream.id)) or ProviderHealth(upstream_model_id=candidate.upstream.id)
    breaker=_circuit_breaker(db,candidate.upstream.id)
    if success:
        row.success_count=(row.success_count or 0)+1;row.last_success_at=utc_now();row.avg_latency_ms=latency_ms if row.avg_latency_ms is None else (row.avg_latency_ms*0.8+latency_ms*0.2)
        breaker.state="closed";breaker.opened_at=None;breaker.half_open_at=None;breaker.consecutive_failures=0
    else:
        row.failure_count=(row.failure_count or 0)+1;row.last_failure_at=utc_now();row.last_failure_reason=error
        if trip_breaker:
            breaker.consecutive_failures=(breaker.consecutive_failures or 0)+1
            if breaker.state=="half_open" or breaker.consecutive_failures>=(breaker.failure_threshold or 3):
                breaker.state="open";breaker.opened_at=utc_now();breaker.half_open_at=None
        else:
            # Authentication, unsupported-model and protocol/configuration
            # failures prove the endpoint is reachable. They are deterministic
            # for this request and must not poison provider availability.
            breaker.state="closed";breaker.opened_at=None;breaker.half_open_at=None;breaker.consecutive_failures=0
    db.add(row);db.add(breaker)


def _trips_breaker(exc:ProtocolError)->bool:
    if exc.error_type in {"provider_timeout","provider_unavailable"}:return True
    if exc.error_type=="upstream_http_error":
        status=int(exc.details.get("status_code") or 0)
        return status in {408,429} or status>=500
    return False


def _open_breaker_immediately(db:Session,candidate:RouteCandidate)->None:
    """Skip a deterministically unusable upstream for its configured cooldown."""
    breaker=_circuit_breaker(db,candidate.upstream.id)
    breaker.state="open";breaker.opened_at=utc_now();breaker.half_open_at=None
    breaker.consecutive_failures=max(breaker.consecutive_failures or 0,breaker.failure_threshold or 3)
    db.add(breaker)


def _requires_immediate_cooldown(exc:ProtocolError)->bool:
    """Avoid retrying quota exhaustion and broken model/protocol routes per request."""
    if exc.error_type!="upstream_http_error":return False
    return int(exc.details.get("status_code") or 0) in {404,405,429}


def _all_candidate_error(last_error:ProtocolError,explanation:list[dict[str,Any]])->ProtocolError:
    """Summarize a failed fallback chain instead of exposing only its final error."""
    failures=[item for item in explanation if item.get("stage")]
    if len(failures)<=1:
        return ProtocolError(last_error.error_type,str(last_error),last_error.stage,{**last_error.details,"candidates":explanation})
    status_counts:dict[str,int]={};error_counts:dict[str,int]={};attempts=[]
    for item in failures:
        details=item.get("details") if isinstance(item.get("details"),dict) else {}
        status=details.get("status_code")
        if status is not None:
            key=str(status);status_counts[key]=status_counts.get(key,0)+1
        reason=(item.get("reasons") or ["运行时失败：unknown"])[0]
        error_type=str(reason).removeprefix("运行时失败：")
        error_counts[error_type]=error_counts.get(error_type,0)+1
        attempt={
            "candidate_id":item.get("candidate_id"),
            "provider_instance_id":item.get("provider_instance_id"),
            "provider_name":item.get("provider_name"),
            "upstream_model_id":item.get("upstream_model_id"),
            "upstream_model":item.get("upstream_model"),
            "error_type":error_type,
            "stage":item.get("stage"),
        }
        for key in ("status_code","upstream_error_code"):
            if details.get(key) is not None:attempt[key]=details[key]
        upstream_message=details.get("upstream_error_message")
        if upstream_message:attempt["upstream_error_message"]=str(upstream_message)[:300]
        attempts.append(attempt)
    statuses={int(value) for value in status_counts}
    representative_status=429 if 429 in statuses else 408 if 408 in statuses else max(statuses,default=0)
    details={
        "cause":"all_upstream_candidates_failed",
        "failure_count":len(failures),
        "status_counts":status_counts,
        "error_counts":error_counts,
        "upstream_statuses":sorted(statuses),
        "attempts":attempts,
    }
    if representative_status:details["status_code"]=representative_status
    return ProtocolError("all_upstream_candidates_failed","统一模型的全部候选调用失败","upstream_call",details)


def _budgets(db:Session,request:CanonicalRequest,unified:UnifiedModel,api_token_id:int|None,provider_id:int|None=None,upstream_model_id:int|None=None)->list[Budget]:
    return matching_budgets(db,api_token_id=api_token_id,provider_id=provider_id,upstream_model_id=upstream_model_id,unified_model=request.unified_model,unified_model_id=unified.id)


def _exceeded(rows:list[Budget])->list[Budget]:
    return [row for row in rows if budget_is_exceeded(row)]


def _candidate_unit_cost(candidate:RouteCandidate)->float:
    return (candidate.upstream.input_price or 0)+(candidate.upstream.output_price or 0)


def _apply_exceeded_budget_actions(rows:list[Budget],candidates:list[RouteCandidate])->list[RouteCandidate]:
    actions={row.enforcement_action for row in rows}
    if "reject" in actions:
        raise ProtocolError("budget_exceeded","请求已被预算策略拒绝","budget_check",{"budget_ids":[row.id for row in rows if row.enforcement_action=="reject"]})
    if actions & {"fallback_to_free"}:
        free=[candidate for candidate in candidates if _candidate_unit_cost(candidate)<=0]
        if not free:
            raise ProtocolError("budget_exceeded","预算要求回退免费候选，但没有满足能力和协议的免费候选","budget_check",{"budget_ids":[row.id for row in rows if row.enforcement_action=="fallback_to_free"]})
        candidates=free
    if actions & {"fallback_to_cheapest","degrade"}:
        candidates=sorted(candidates,key=lambda item:(_candidate_unit_cost(item),item.candidate.priority,item.candidate.id))
    return candidates


async def execute_request(db:Session,request:CanonicalRequest,api_token_id:int|None=None)->tuple[dict[str,Any],CanonicalResponse]:
    request_id=f"req_{uuid.uuid4().hex}";started=utc_now();clock=time.perf_counter();selected:RouteCandidate|None=None;explanation=[];auxiliary={};unified=None;first_token_latency_ms:float|None=None
    token_row=db.get(ApiToken,api_token_id) if api_token_id else None;token_prefix_snapshot=token_row.token_prefix if token_row else None
    try:
        unified,candidates,explanation=route_candidates(db,request)
        preflight=_exceeded(_budgets(db,request,unified,api_token_id))
        candidates=_apply_exceeded_budget_actions(preflight,candidates)
        auxiliary=plan_auxiliary(db,request,unified,candidates);request,terminal_response=await _run_auxiliary_steps(db,request,auxiliary,parent_request_id=request_id,api_token_id=api_token_id,token_prefix_snapshot=token_prefix_snapshot);last_error:ProtocolError|None=None
        for candidate in candidates:
            selected=candidate;attempt=time.perf_counter()
            scoped_rejected=[row for row in _exceeded(_budgets(db,request,unified,api_token_id,candidate.provider.id,candidate.upstream.id)) if row.scope in {"provider","provider_instance","upstream_model"} and row.enforcement_action in {"reject","fallback_to_free","fallback_to_cheapest","degrade"}]
            if scoped_rejected:
                scopes={row.scope for row in scoped_rejected};reason="上游模型预算已耗尽" if "upstream_model" in scopes else "供应商预算已耗尽"
                last_error=ProtocolError("budget_exceeded",reason,"budget_check",{"budget_ids":[row.id for row in scoped_rejected],"provider_instance_id":candidate.provider.id,"upstream_model_id":candidate.upstream.id});explanation.append({"candidate_id":candidate.candidate.id,"eligible":False,"reasons":[reason]});continue
            try:
                response=terminal_response or await _call_http(candidate,request);latency=(time.perf_counter()-attempt)*1000
                first_token_latency_ms=(time.perf_counter()-clock)*1000
                _health(db,candidate,True,latency);break
            except ProtocolError as exc:
                last_error=exc;_health(db,candidate,False,(time.perf_counter()-attempt)*1000,str(exc),_trips_breaker(exc))
                if _requires_immediate_cooldown(exc):_open_breaker_immediately(db,candidate)
                explanation.append({"candidate_id":candidate.candidate.id,"upstream_model_id":candidate.upstream.id,"upstream_model":candidate.upstream.model_id,"provider_instance_id":candidate.provider.id,"provider_name":candidate.provider.name,"eligible":False,"reasons":[f"运行时失败：{exc.error_type}"],"stage":exc.stage,"details":exc.details})
        else:
            if last_error:
                raise _all_candidate_error(last_error,explanation)
            raise ProtocolError("provider_unavailable","统一模型的全部候选调用失败","upstream_call",{"candidates":explanation})
        if any(step.get("workflow_type")=="structured_repair" for step in auxiliary.get("steps",[])):
            request,repaired=await _run_auxiliary_steps(db,request,auxiliary,parent_request_id=request_id,api_token_id=api_token_id,token_prefix_snapshot=token_prefix_snapshot,post_response=response);response=repaired or response
        usage=response.get("usage") or {};input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0);output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        cost=(input_tokens*(selected.upstream.input_price or 0)+output_tokens*(selected.upstream.output_price or 0))/1_000_000
        accumulate_budget_spend(db,estimated_cost=cost,api_token_id=api_token_id,provider_id=selected.provider.id,upstream_model_id=selected.upstream.id,unified_model=request.unified_model,unified_model_id=unified.id)
        remember_session_candidate(unified,request,selected.candidate.id)
        latency_ms=(time.perf_counter()-clock)*1000
        db.add(RequestLog(request_id=request_id,started_at=started,finished_at=utc_now(),inbound_protocol=request.inbound_protocol,unified_model=request.unified_model,provider_instance_id=selected.provider.id,upstream_model_id=selected.upstream.id,combo_strategy=unified.combo_strategy,candidate_summary_json=explanation,auxiliary_summary_json=auxiliary,api_token_id=api_token_id,api_token_prefix_snapshot=token_prefix_snapshot,input_tokens=input_tokens,output_tokens=output_tokens,estimated_cost=cost,success=True,latency_ms=latency_ms,first_token_latency_ms=first_token_latency_ms))
        db.add(UsageHistory(request_id=request_id,api_token_id=api_token_id,provider_instance_id=selected.provider.id,upstream_model_id=selected.upstream.id,unified_model=request.unified_model,inbound_protocol=request.inbound_protocol,input_tokens=input_tokens,output_tokens=output_tokens,estimated_cost=cost));db.commit()
        return {"request_id":request_id,"selected":selected,"auxiliary":auxiliary,"explanation":explanation},response
    except ProtocolError as exc:
        failure_candidates=explanation or (exc.details.get("candidates") if isinstance(exc.details,dict) else None)
        db.add(RequestLog(request_id=request_id,started_at=started,finished_at=utc_now(),inbound_protocol=request.inbound_protocol,unified_model=request.unified_model,provider_instance_id=selected.provider.id if selected else None,upstream_model_id=selected.upstream.id if selected else None,combo_strategy=unified.combo_strategy if unified else None,candidate_summary_json=failure_candidates or None,auxiliary_summary_json=auxiliary or None,api_token_id=api_token_id,api_token_prefix_snapshot=token_prefix_snapshot,success=False,error_type=exc.error_type,error_message=str(exc),failure_stage=exc.stage,latency_ms=(time.perf_counter()-clock)*1000));db.commit();raise

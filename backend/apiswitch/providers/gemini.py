import time
import uuid
from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import ChatCompletionRequest


DEFAULT_GEMINI_MODELS = [
    {"id": "gemini-1.5-pro", "owned_by": "google", "capabilities": ["text", "vision"]},
    {"id": "gemini-1.5-flash", "owned_by": "google", "capabilities": ["text", "vision"]},
    {"id": "gemini-2.0-flash", "owned_by": "google", "capabilities": ["text", "vision"]},
]


class GeminiProviderAdapter(ProviderAdapter):
    name = "gemini"
    provider_type = "gemini"

    def __init__(self, base_url: str, api_key: str | None, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise ProviderError("Missing Gemini API key", "missing_api_key")
        return self.api_key

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        if request.stream:
            raise ProviderError("Gemini streaming is not implemented yet", "streaming_not_implemented")
        api_key = self._require_api_key()
        payload = _openai_chat_to_gemini_payload(request)
        url = f"{self.base_url}/models/{request.model}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini generateContent request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Gemini generateContent failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return _gemini_response_to_openai_chat(response.json(), request.model)

    async def list_models(self) -> list[dict[str, Any]]:
        if not self.api_key:
            return DEFAULT_GEMINI_MODELS
        url = f"{self.base_url}/models?key={self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini model discovery failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Gemini model discovery failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        payload = response.json()
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise ProviderError("Gemini /models response models is not a list", "invalid_upstream_response")
        return [_normalize_gemini_model(item) for item in models if isinstance(item, dict)]


def _openai_chat_to_gemini_payload(request: ChatCompletionRequest) -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    system_parts: list[dict[str, str]] = []
    for message in request.messages:
        role = message.role
        text = _message_content_to_text(message.content)
        if role == "system":
            if text:
                system_parts.append({"text": text})
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})

    payload: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}
    generation_config: dict[str, Any] = {}
    if request.temperature is not None:
        generation_config["temperature"] = request.temperature
    if request.top_p is not None:
        generation_config["topP"] = request.top_p
    if request.max_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_tokens
    if generation_config:
        payload["generationConfig"] = generation_config
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    return payload


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text"} and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _gemini_response_to_openai_chat(payload: dict[str, Any], model: str) -> dict[str, Any]:
    candidates = payload.get("candidates") or []
    candidate = candidates[0] if candidates else {}
    content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    finish_reason = _gemini_finish_reason_to_openai(candidate.get("finishReason") if isinstance(candidate, dict) else None)
    usage = payload.get("usageMetadata", {}) if isinstance(payload.get("usageMetadata"), dict) else {}
    prompt_tokens = usage.get("promptTokenCount")
    completion_tokens = usage.get("candidatesTokenCount")
    total_tokens = usage.get("totalTokenCount")
    return {
        "id": f"chatcmpl_gemini_{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
            "total_tokens": total_tokens or ((prompt_tokens or 0) + (completion_tokens or 0)),
        },
    }


def _gemini_finish_reason_to_openai(reason: str | None) -> str:
    if reason in {"STOP", "MAX_TOKENS"}:
        return "stop" if reason == "STOP" else "length"
    if reason in {"SAFETY", "RECITATION"}:
        return "content_filter"
    return "stop"


def _normalize_gemini_model(item: dict[str, Any]) -> dict[str, Any]:
    raw_name = str(item.get("name") or item.get("id") or "")
    model_id = raw_name.split("/")[-1] if raw_name else "unknown"
    methods = item.get("supportedGenerationMethods") or []
    capabilities = ["text"]
    if "generateContent" in methods:
        capabilities.append("chat")
    return {"id": model_id, "owned_by": "google", "capabilities": capabilities}

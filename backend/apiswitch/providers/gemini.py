import time
import uuid
import json
from collections.abc import AsyncIterator
from collections.abc import Callable
from datetime import datetime, timedelta
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

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_seconds: int = 120,
        *,
        oauth_refresh_token: str | None = None,
        oauth_client_id: str | None = None,
        oauth_project_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_expires_at: datetime | None = None,
        on_oauth_refresh: Callable[[str, str | None, datetime | None], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.oauth_refresh_token = oauth_refresh_token
        self.oauth_client_id = oauth_client_id
        self.oauth_project_id = oauth_project_id
        self.oauth_client_secret = oauth_client_secret
        self.oauth_expires_at = oauth_expires_at
        self.on_oauth_refresh = on_oauth_refresh

    @property
    def using_oauth(self) -> bool:
        return bool(self.oauth_client_id and self.oauth_refresh_token)

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise ProviderError("Missing Gemini API key", "missing_api_key")
        return self.api_key

    async def _oauth_headers(self) -> dict[str, str]:
        if not self.using_oauth:
            return {}
        if not self.api_key or (
            self.oauth_expires_at is not None and self.oauth_expires_at <= datetime.utcnow() + timedelta(seconds=60)
        ):
            await self._refresh_oauth_access_token()
        if not self.api_key:
            raise ProviderError("Missing Gemini OAuth access token", "missing_oauth_access_token")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.oauth_project_id:
            headers["x-goog-user-project"] = self.oauth_project_id
        return headers

    async def _refresh_oauth_access_token(self) -> None:
        if not self.oauth_refresh_token or not self.oauth_client_id:
            raise ProviderError("Missing Gemini OAuth refresh configuration", "missing_oauth_refresh_config")
        data = {
            "client_id": self.oauth_client_id,
            "refresh_token": self.oauth_refresh_token,
            "grant_type": "refresh_token",
        }
        if self.oauth_client_secret:
            data["client_secret"] = self.oauth_client_secret
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post("https://oauth2.googleapis.com/token", data=data)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini OAuth refresh failed: {exc}", "oauth_refresh_failed") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"Gemini OAuth refresh failed with status {response.status_code}: {response.text}",
                "oauth_refresh_failed",
            )
        try:
            payload = response.json()
            access_token = str(payload["access_token"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Gemini OAuth refresh returned no access token", "oauth_refresh_failed") from exc
        refresh_token = payload.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            self.oauth_refresh_token = refresh_token
        expires_in = payload.get("expires_in")
        self.oauth_expires_at = (
            datetime.utcnow() + timedelta(seconds=int(expires_in)) if isinstance(expires_in, (int, float)) else None
        )
        self.api_key = access_token
        if self.on_oauth_refresh is not None:
            self.on_oauth_refresh(self.api_key, self.oauth_refresh_token, self.oauth_expires_at)

    async def _request_url_and_headers(self, path: str) -> tuple[str, dict[str, str]]:
        if self.using_oauth:
            return f"{self.base_url}{path}", await self._oauth_headers()
        separator = "&" if "?" in path else "?"
        return f"{self.base_url}{path}{separator}key={self._require_api_key()}", {}

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        if request.stream:
            raise ProviderError("Use stream_chat for Gemini streaming requests", "invalid_stream_path")
        payload = _openai_chat_to_gemini_payload(request)
        url, headers = await self._request_url_and_headers(f"/models/{request.model}:generateContent")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini generateContent request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Gemini generateContent failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return _gemini_response_to_openai_chat(response.json(), request.model)

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        """Bridge Gemini ``streamGenerateContent`` SSE to OpenAI Chat SSE."""
        payload = _openai_chat_to_gemini_payload(request)
        url, headers = await self._request_url_and_headers(
            f"/models/{request.model}:streamGenerateContent?alt=sse"
        )
        stream_id = f"chatcmpl_gemini_{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        buffer = ""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload, headers=headers, timeout=self.timeout_seconds) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderError(
                            f"Gemini streamGenerateContent failed with status {response.status_code}: "
                            f"{body.decode('utf-8', errors='ignore')}",
                            "upstream_http_error",
                        )
                    self.record_response_headers(response.headers)
                    async for raw_chunk in response.aiter_text():
                        buffer += raw_chunk
                        while "\n\n" in buffer:
                            event, buffer = buffer.split("\n\n", 1)
                            converted = _gemini_sse_event_to_openai(event, stream_id, created, request.model)
                            if converted is not None:
                                yield converted
            if buffer.strip():
                converted = _gemini_sse_event_to_openai(buffer, stream_id, created, request.model)
                if converted is not None:
                    yield converted
            yield b"data: [DONE]\n\n"
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini streamGenerateContent request failed: {exc}") from exc

    async def list_models(self) -> list[dict[str, Any]]:
        if not self.api_key and not self.using_oauth:
            return DEFAULT_GEMINI_MODELS
        url, headers = await self._request_url_and_headers("/models")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers=headers)
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


def _gemini_sse_event_to_openai(
    event: str, stream_id: str, created: int, model: str
) -> bytes | None:
    payload: dict[str, Any] | None = None
    for line in event.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            candidate = json.loads(line[len("data:") :].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        return None
    candidates = payload.get("candidates", [])
    candidate = candidates[0] if isinstance(candidates, list) and candidates else {}
    content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    finish_reason = (
        _gemini_finish_reason_to_openai(candidate.get("finishReason"))
        if isinstance(candidate, dict) and candidate.get("finishReason")
        else None
    )
    usage_metadata = payload.get("usageMetadata", {})
    usage = None
    if isinstance(usage_metadata, dict):
        prompt = usage_metadata.get("promptTokenCount")
        completion = usage_metadata.get("candidatesTokenCount")
        total = usage_metadata.get("totalTokenCount")
        if any(isinstance(value, int) for value in (prompt, completion, total)):
            usage = {
                "prompt_tokens": prompt or 0,
                "completion_tokens": completion or 0,
                "total_tokens": total or ((prompt or 0) + (completion or 0)),
            }
    if not text and finish_reason is None and usage is None:
        return None
    chunk: dict[str, Any] = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"content": text} if text else {}, "finish_reason": finish_reason}],
    }
    if usage is not None:
        chunk["usage"] = usage
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")


def _normalize_gemini_model(item: dict[str, Any]) -> dict[str, Any]:
    raw_name = str(item.get("name") or item.get("id") or "")
    model_id = raw_name.split("/")[-1] if raw_name else "unknown"
    methods = item.get("supportedGenerationMethods") or []
    capabilities = ["text"]
    if "generateContent" in methods:
        capabilities.append("chat")
    return {"id": model_id, "owned_by": "google", "capabilities": capabilities}

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    stream_options: dict[str, Any] | None = None
    file_ids: list[str] | None = None


class ResponsesRequest(BaseModel):
    model: str
    input: Any
    stream: bool = False
    instructions: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    previous_response_id: str | None = None


class AnthropicMessagesRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int = Field(default=1024, ge=1)
    stream: bool = False
    system: str | None = None
    tools: list[dict[str, Any]] | None = None


class EmbeddingsRequest(BaseModel):
    model: str
    input: Any
    encoding_format: Literal["float", "base64"] | None = None
    dimensions: int | None = Field(default=None, ge=1)
    user: str | None = None


class ImageGenerationRequest(BaseModel):
    """OpenAI-compatible image generation input routed through a Unified Model."""

    model: str
    prompt: str = Field(min_length=1, max_length=32_000)
    n: int | None = Field(default=None, ge=1, le=10)
    size: str | None = None
    quality: str | None = None
    style: str | None = None
    response_format: Literal["url", "b64_json"] | None = None
    user: str | None = None


class ImageEditRequest(BaseModel):
    """OpenAI-compatible multipart image-edit request."""

    model: str
    prompt: str = Field(min_length=1, max_length=32_000)
    filename: str
    content_type: str | None = None
    image_bytes: bytes = Field(exclude=True)
    mask_filename: str | None = None
    mask_content_type: str | None = None
    mask_bytes: bytes | None = Field(default=None, exclude=True)
    n: int | None = Field(default=None, ge=1, le=10)
    size: str | None = None
    response_format: Literal["url", "b64_json"] | None = None
    user: str | None = None


class ImageVariationRequest(BaseModel):
    """OpenAI-compatible multipart image-variation request."""

    model: str
    filename: str
    content_type: str | None = None
    image_bytes: bytes = Field(exclude=True)
    n: int | None = Field(default=None, ge=1, le=10)
    size: str | None = None
    response_format: Literal["url", "b64_json"] | None = None
    user: str | None = None


class VideoGenerationRequest(BaseModel):
    """APISwitch video-generation extension with an OpenAI-style envelope."""

    model: str
    prompt: str = Field(min_length=1, max_length=32_000)
    seconds: int | None = Field(default=None, ge=1, le=120)
    size: str | None = None
    n: int | None = Field(default=None, ge=1, le=4)
    user: str | None = None


class MusicGenerationRequest(BaseModel):
    """APISwitch music-generation extension for providers without a shared standard."""

    model: str
    prompt: str = Field(min_length=1, max_length=32_000)
    duration_seconds: int | None = Field(default=None, ge=1, le=600)
    lyrics: str | None = Field(default=None, max_length=32_000)
    instrumental: bool | None = None
    n: int | None = Field(default=None, ge=1, le=4)
    user: str | None = None


class AudioSpeechRequest(BaseModel):
    model: str
    input: str = Field(min_length=1, max_length=32_000)
    voice: str
    response_format: str | None = None
    speed: float | None = Field(default=None, ge=0.25, le=4.0)


class AudioTranscriptionRequest(BaseModel):
    """Internal representation of an OpenAI multipart transcription request."""

    model: str
    filename: str
    content_type: str | None = None
    file_bytes: bytes = Field(exclude=True)
    language: str | None = None
    prompt: str | None = None
    response_format: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=1)


class ModerationRequest(BaseModel):
    model: str
    input: Any


class RerankRequest(BaseModel):
    model: str
    query: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    top_n: int | None = Field(default=None, ge=1)


class SearchRequest(BaseModel):
    model: str
    query: str = Field(min_length=1)
    max_results: int = Field(default=10, ge=1, le=50)


class GeminiGenerateContentRequest(BaseModel):
    contents: list[dict[str, Any]]
    systemInstruction: dict[str, Any] | None = None
    generationConfig: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    toolConfig: dict[str, Any] | None = None
    safetySettings: list[dict[str, Any]] | None = None


class NormalizedRequest(BaseModel):
    inbound_protocol: Literal[
        "openai_chat",
        "openai_responses",
        "anthropic_messages",
        "openai_embeddings",
        "gemini_v1beta",
    ]
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    raw: dict[str, Any]

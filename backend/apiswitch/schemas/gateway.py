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


class NormalizedRequest(BaseModel):
    inbound_protocol: Literal[
        "openai_chat",
        "openai_responses",
        "anthropic_messages",
        "openai_embeddings",
    ]
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    raw: dict[str, Any]

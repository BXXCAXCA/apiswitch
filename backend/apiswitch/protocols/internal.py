from dataclasses import dataclass, field
from typing import Any


@dataclass
class InternalMessage:
    role: str
    content: Any


@dataclass
class InternalToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class InternalRequest:
    model: str
    messages: list[InternalMessage]
    stream: bool = False
    tools: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalResponse:
    model: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None

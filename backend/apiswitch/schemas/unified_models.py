from typing import Any

from pydantic import BaseModel, Field


class UnifiedModelCreate(BaseModel):
    name: str
    description: str | None = None
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)


class UnifiedModelRead(UnifiedModelCreate):
    id: int
    candidates: list[dict[str, Any]] = Field(default_factory=list)

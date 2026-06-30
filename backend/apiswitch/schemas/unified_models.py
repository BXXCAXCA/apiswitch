from typing import Any

from pydantic import BaseModel


class UnifiedModelCreate(BaseModel):
    name: str
    description: str | None = None
    enabled: bool = True
    capabilities: list[str] = []


class UnifiedModelRead(UnifiedModelCreate):
    id: int
    candidates: list[dict[str, Any]] = []

from typing import Any

from pydantic import BaseModel, Field


class UnifiedModelCreate(BaseModel):
    name: str
    description: str | None = None
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)


class UnifiedModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    capabilities: list[str] | None = None


class UnifiedModelRead(UnifiedModelCreate):
    id: int
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class UnifiedModelCandidateCreate(BaseModel):
    provider_id: int
    provider_connection_id: int | None = None
    provider_node_id: int | None = None
    upstream_model: str
    manual_priority: int = 100
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)


class UnifiedModelCandidateUpdate(BaseModel):
    provider_id: int | None = None
    provider_connection_id: int | None = None
    provider_node_id: int | None = None
    upstream_model: str | None = None
    manual_priority: int | None = None
    enabled: bool | None = None
    capabilities: list[str] | None = None


class UnifiedModelCandidateRead(BaseModel):
    id: int
    unified_model_id: int
    provider_id: int
    provider_name: str
    provider_type: str
    provider_connection_id: int | None = None
    provider_node_id: int | None = None
    upstream_model: str
    manual_priority: int
    enabled: bool
    capabilities: list[str] = Field(default_factory=list)

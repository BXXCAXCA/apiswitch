from typing import Any, Literal

from pydantic import BaseModel, Field


class UnifiedModelCreate(BaseModel):
    name: str
    description: str | None = None
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)
    routing_mode: Literal["static", "combo", "auto"] = "static"
    combo_strategy: Literal["priority", "weighted", "round_robin", "least_used", "cost_optimized", "quota_headroom", "last_known_good"] = "priority"
    category: str | None = None
    preferred_tier: str = "balanced"
    max_request_cost: float | None = Field(default=None, gt=0)
    min_context_window: int | None = Field(default=None, ge=1)
    session_affinity_enabled: bool = True


class UnifiedModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    capabilities: list[str] | None = None
    routing_mode: Literal["static", "combo", "auto"] | None = None
    combo_strategy: Literal["priority", "weighted", "round_robin", "least_used", "cost_optimized", "quota_headroom", "last_known_good"] | None = None
    category: str | None = None
    preferred_tier: str | None = None
    max_request_cost: float | None = Field(default=None, gt=0)
    min_context_window: int | None = Field(default=None, ge=1)
    session_affinity_enabled: bool | None = None


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

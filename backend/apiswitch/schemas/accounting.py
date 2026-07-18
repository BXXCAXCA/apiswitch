from datetime import datetime

from pydantic import BaseModel, Field


class ModelPricingCreate(BaseModel):
    provider_id: int | None = None
    model_name: str
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    cached_input_cost_per_million: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    effective_at: datetime | None = None


class ModelPricingUpdate(BaseModel):
    provider_id: int | None = None
    model_name: str | None = None
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    cached_input_cost_per_million: float | None = Field(default=None, ge=0)
    currency: str | None = None
    effective_at: datetime | None = None


class ModelPricingRead(BaseModel):
    id: int
    provider_id: int | None
    model_name: str
    input_cost_per_million: float | None
    output_cost_per_million: float | None
    cached_input_cost_per_million: float | None
    currency: str
    source: str
    source_url: str | None
    effective_at: datetime
    created_at: datetime
    updated_at: datetime


class ModelPricingCatalogEntry(BaseModel):
    model_name: str
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    cached_input_cost_per_million: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    effective_at: datetime | None = None


class ModelPricingCatalogImport(BaseModel):
    provider_id: int | None = None
    source: str = Field(min_length=1, max_length=64)
    source_url: str | None = Field(default=None, max_length=1024)
    entries: list[ModelPricingCatalogEntry] = Field(min_length=1)


class QuotaSnapshotCreate(BaseModel):
    provider_connection_id: int
    remaining_requests: int | None = Field(default=None, ge=0)
    remaining_tokens: int | None = Field(default=None, ge=0)
    remaining_credit: float | None = Field(default=None, ge=0)
    reset_at: datetime | None = None
    raw: dict = Field(default_factory=dict)


class QuotaSnapshotRead(BaseModel):
    id: int
    provider_connection_id: int
    captured_at: datetime
    remaining_requests: int | None
    remaining_tokens: int | None
    remaining_credit: float | None
    reset_at: datetime | None
    raw: dict


class UsageHistoryRead(BaseModel):
    id: int
    request_id: str
    api_token_id: int | None
    provider_connection_id: int | None
    unified_model: str
    upstream_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    created_at: datetime


class UsageSummary(BaseModel):
    request_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    priced_request_count: int

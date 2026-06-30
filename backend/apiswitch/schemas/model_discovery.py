from pydantic import BaseModel, Field


class DiscoveredModel(BaseModel):
    id: str
    owned_by: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class ProviderConnectionResult(BaseModel):
    provider_id: int
    provider_name: str
    provider_type: str
    ok: bool
    message: str


class ModelDiscoveryResult(BaseModel):
    provider_id: int
    provider_name: str
    provider_type: str
    models: list[DiscoveredModel]

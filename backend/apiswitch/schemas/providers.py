from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    type: str
    base_url: str
    enabled: bool = True
    timeout_seconds: int = 120
    proxy_type: str | None = None
    proxy_url: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = None
    proxy_type: str | None = None
    proxy_url: str | None = None


class ProviderRead(ProviderCreate):
    id: int

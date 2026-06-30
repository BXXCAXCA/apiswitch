from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    type: str
    base_url: str
    enabled: bool = True
    timeout_seconds: int = 120
    proxy_type: str | None = None
    proxy_url: str | None = None


class ProviderRead(ProviderCreate):
    id: int

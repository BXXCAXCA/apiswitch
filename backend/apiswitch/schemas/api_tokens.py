from datetime import datetime

from pydantic import BaseModel, Field


class ApiTokenCreate(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=lambda: ["gateway:invoke"])
    expires_at: datetime | None = None


class ApiTokenUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class ApiTokenRead(BaseModel):
    id: int
    name: str
    token_prefix: str
    enabled: bool
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApiTokenCreated(ApiTokenRead):
    token: str

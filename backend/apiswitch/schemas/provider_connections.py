from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProviderConnectionCreate(BaseModel):
    name: str
    auth_type: str = "api_key"
    account_label: str | None = None
    credential: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    priority: int = Field(default=100, ge=0, le=1000)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderConnectionUpdate(BaseModel):
    name: str | None = None
    auth_type: str | None = None
    account_label: str | None = None
    credential: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class ProviderConnectionRead(BaseModel):
    id: int
    provider_id: int
    name: str
    auth_type: str
    account_label: str | None
    credential_configured: bool
    refresh_token_configured: bool
    expires_at: datetime | None
    priority: int
    enabled: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GoogleOAuthStartRequest(BaseModel):
    """Configuration needed to begin a local Google/Gemini OAuth consent flow."""

    name: str = Field(min_length=1, max_length=128)
    client_id: str = Field(min_length=1, max_length=512)
    project_id: str = Field(min_length=1, max_length=256)
    client_secret: str | None = Field(default=None, max_length=512)
    redirect_uri: str = Field(min_length=1, max_length=2048)
    account_label: str | None = Field(default=None, max_length=128)
    scopes: list[str] = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/cloud-platform"],
        min_length=1,
    )
    priority: int = Field(default=100, ge=0, le=1000)


class GoogleOAuthStartResult(BaseModel):
    connection_id: int
    authorization_url: str


class ProviderNodeCreate(BaseModel):
    name: str
    base_url: str
    connection_id: int | None = None
    region: str | None = None
    enabled: bool = True
    weight: int = Field(default=100, ge=0, le=1000)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderNodeUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    connection_id: int | None = None
    region: str | None = None
    enabled: bool | None = None
    weight: int | None = Field(default=None, ge=0, le=1000)
    capabilities: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ProviderNodeRead(BaseModel):
    id: int
    provider_id: int
    connection_id: int | None
    name: str
    base_url: str
    region: str | None
    enabled: bool
    weight: int
    capabilities: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

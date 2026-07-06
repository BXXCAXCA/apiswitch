from typing import Any

from pydantic import BaseModel, Field


class SystemSettings(BaseModel):
    listen_host: str = "127.0.0.1"
    port: int = 8080
    auth_enabled: bool = True
    stream_failure_mode: str = "strict"
    default_timeout_seconds: int = Field(default=120, ge=1)
    request_log_retention_days: int = Field(default=30, ge=1)
    record_full_request: bool = False
    record_full_response: bool = False
    default_provider_type: str = "mock"
    default_unified_model: str = "code-best"


class SettingItem(BaseModel):
    key: str
    value: Any


class SettingsResponse(BaseModel):
    settings: SystemSettings
    raw: dict[str, Any]


class SettingsUpdate(BaseModel):
    listen_host: str | None = None
    port: int | None = Field(default=None, ge=1)
    auth_enabled: bool | None = None
    stream_failure_mode: str | None = None
    default_timeout_seconds: int | None = Field(default=None, ge=1)
    request_log_retention_days: int | None = Field(default=None, ge=1)
    record_full_request: bool | None = None
    record_full_response: bool | None = None
    default_provider_type: str | None = None
    default_unified_model: str | None = None

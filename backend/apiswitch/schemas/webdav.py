from datetime import datetime

from typing import Any, Literal

from pydantic import BaseModel


class WebDAVProfileCreate(BaseModel):
    name: str
    url: str
    username: str | None = None
    password: str | None = None
    enabled: bool = True


class WebDAVProfileUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool | None = None


class WebDAVProfileRead(BaseModel):
    id: int
    name: str
    url: str
    username: str | None
    enabled: bool
    password_configured: bool
    created_at: datetime
    updated_at: datetime


class WebDAVConnectionResult(BaseModel):
    ok: bool
    message: str
    status_code: int | None = None


class WebDAVImportOptions(BaseModel):
    conflict_strategy: Literal["abort", "remote_wins", "local_wins"] = "abort"


class WebDAVSyncLogRead(BaseModel):
    id: int
    profile_id: int
    operation: str
    success: bool
    conflict_strategy: str | None
    summary: dict[str, Any]
    error_message: str | None
    created_at: datetime

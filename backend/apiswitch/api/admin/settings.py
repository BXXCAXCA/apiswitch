from fastapi import APIRouter

from apiswitch.config import settings

router = APIRouter(prefix="/api/admin/settings", tags=["Admin - Settings"])

_RUNTIME_SETTINGS = {
    "listen_host": settings.listen_host,
    "port": settings.port,
    "auth_enabled": settings.auth_enabled,
    "stream_failure_mode": settings.stream_failure_mode,
    "record_full_request": False,
    "record_full_response": False,
}


@router.get("")
async def get_settings() -> dict:
    return _RUNTIME_SETTINGS


@router.patch("")
async def update_settings(payload: dict) -> dict:
    _RUNTIME_SETTINGS.update(payload)
    return _RUNTIME_SETTINGS

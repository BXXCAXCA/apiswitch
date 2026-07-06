from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.schemas.settings import SettingsResponse, SettingsUpdate
from apiswitch.services.settings import get_system_settings, list_raw_settings, update_system_settings

router = APIRouter(prefix="/api/admin/settings", tags=["Admin - Settings"])


@router.get("")
async def get_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    return SettingsResponse(settings=get_system_settings(db), raw=list_raw_settings(db))


@router.patch("")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsResponse:
    values = payload.model_dump(exclude_unset=True)
    settings = update_system_settings(db, values)
    return SettingsResponse(settings=settings, raw=list_raw_settings(db))

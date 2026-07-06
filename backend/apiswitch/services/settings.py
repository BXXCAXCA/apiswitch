from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.config import settings as app_settings
from apiswitch.db.models import Setting
from apiswitch.schemas.settings import SystemSettings

DEFAULT_SETTINGS = SystemSettings(
    listen_host=app_settings.listen_host,
    port=app_settings.port,
    auth_enabled=app_settings.auth_enabled,
    stream_failure_mode=app_settings.stream_failure_mode,
)


def _value_to_setting(value: Any) -> dict[str, Any]:
    return {"value": value}


def _setting_to_value(setting: Setting) -> Any:
    if not setting.value_json:
        return None
    return setting.value_json.get("value")


def list_raw_settings(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(Setting).order_by(Setting.key)).all()
    return {row.key: _setting_to_value(row) for row in rows}


def get_system_settings(db: Session) -> SystemSettings:
    raw = list_raw_settings(db)
    return SystemSettings(**{**DEFAULT_SETTINGS.model_dump(), **raw})


def upsert_setting(db: Session, key: str, value: Any) -> None:
    setting = db.get(Setting, key)
    if setting is None:
        setting = Setting(key=key, value_json=_value_to_setting(value))
        db.add(setting)
    else:
        setting.value_json = _value_to_setting(value)


def update_system_settings(db: Session, values: dict[str, Any]) -> SystemSettings:
    for key, value in values.items():
        upsert_setting(db, key, value)
    db.commit()
    return get_system_settings(db)


def seed_default_settings(db: Session) -> None:
    existing = list_raw_settings(db)
    for key, value in DEFAULT_SETTINGS.model_dump().items():
        if key not in existing:
            upsert_setting(db, key, value)
    db.commit()

from typing import Any

from apiswitch.webdav.export import CONFIG_SCHEMA_VERSION


def validate_config_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("Unsupported APISwitch config schema version")
    if payload.get("export_type") != "apiswitch_config":
        raise ValueError("Unsupported APISwitch export type")

from typing import Any


CONFIG_SCHEMA_VERSION = "v0.1"


def build_export_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "export_type": "apiswitch_config",
        "config": config,
    }

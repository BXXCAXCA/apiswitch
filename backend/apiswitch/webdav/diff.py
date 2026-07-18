from typing import Any


def diff_config(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, list[str]]:
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []

    def compare(current_value: Any, incoming_value: Any, path: str) -> None:
        if isinstance(current_value, dict) and isinstance(incoming_value, dict):
            current_keys = set(current_value)
            incoming_keys = set(incoming_value)
            added.extend(f"{path}.{key}" if path else str(key) for key in sorted(incoming_keys - current_keys))
            removed.extend(f"{path}.{key}" if path else str(key) for key in sorted(current_keys - incoming_keys))
            for key in sorted(current_keys & incoming_keys):
                compare(current_value[key], incoming_value[key], f"{path}.{key}" if path else str(key))
        elif current_value != incoming_value:
            changed.append(path)

    compare(current, incoming, "")
    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "changed": sorted(changed),
    }

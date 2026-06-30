from typing import Any


def diff_config(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, list[str]]:
    current_keys = set(current.keys())
    incoming_keys = set(incoming.keys())
    changed = [key for key in sorted(current_keys & incoming_keys) if current[key] != incoming[key]]
    return {
        "added": sorted(incoming_keys - current_keys),
        "removed": sorted(current_keys - incoming_keys),
        "changed": changed,
    }

from fastapi import APIRouter, HTTPException, status

from apiswitch.providers.catalog import get_provider_catalog_item, list_provider_catalog
from apiswitch.providers.factory import OPENAI_COMPATIBLE_PROVIDER_TYPES

router = APIRouter(prefix="/api/admin/provider-catalog", tags=["Admin - Providers"])


def _runtime_item(item: dict) -> dict:
    result = dict(item)
    if result["type"] in OPENAI_COMPATIBLE_PROVIDER_TYPES:
        result["status"] = "implemented"
        result["adapter_mode"] = "openai_compatible"
        result["protocols"] = ["chat", "models"]
    else:
        result["adapter_mode"] = "native" if result["status"] == "implemented" else "planned"
    return result


@router.get("")
async def list_catalog() -> list[dict]:
    return [_runtime_item(item) for item in list_provider_catalog()]


@router.get("/{provider_type}")
async def get_catalog_item(provider_type: str) -> dict:
    item = get_provider_catalog_item(provider_type)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider type not found")
    return _runtime_item(item)

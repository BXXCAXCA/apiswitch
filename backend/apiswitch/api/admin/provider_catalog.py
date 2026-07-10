from fastapi import APIRouter, HTTPException, status

from apiswitch.providers.catalog import get_provider_catalog_item, list_provider_catalog

router = APIRouter(prefix="/api/admin/provider-catalog", tags=["Admin - Providers"])


@router.get("")
async def list_catalog() -> list[dict]:
    return list_provider_catalog()


@router.get("/{provider_type}")
async def get_catalog_item(provider_type: str) -> dict:
    item = get_provider_catalog_item(provider_type)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider type not found")
    return item

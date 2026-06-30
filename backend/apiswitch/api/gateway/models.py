from fastapi import APIRouter

from apiswitch.providers.registry import provider_registry

router = APIRouter(prefix="/v1", tags=["Gateway - Models"])


@router.get("/models")
async def list_models() -> dict:
    models = await provider_registry.get("mock").list_models()
    return {"object": "list", "data": models}

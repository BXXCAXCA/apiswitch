from fastapi import APIRouter, Depends

from apiswitch.api.deps import require_gateway_token
from apiswitch.providers.registry import provider_registry

router = APIRouter(prefix="/v1", tags=["Gateway - Models"])


@router.get("/models")
async def list_models(_auth=Depends(require_gateway_token)) -> dict:
    models = await provider_registry.get("mock").list_models()
    return {"object": "list", "data": models}

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db, require_gateway_token
from apiswitch.db.models import ApiToken
from apiswitch.gateway.errors import GatewayError
from apiswitch.gateway.responses_executor import execute_responses
from apiswitch.providers.base import ProviderError
from apiswitch.schemas.gateway import ResponsesRequest

router = APIRouter(prefix="/v1", tags=["Gateway - OpenAI Responses"])


@router.post("/responses")
async def create_response(
    payload: ResponsesRequest,
    db: Session = Depends(get_db),
    api_token: ApiToken = Depends(require_gateway_token),
) -> dict:
    try:
        return await execute_responses(payload, db, api_token_id=api_token.id)
    except GatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": exc.error_type, "message": str(exc)},
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": exc.error_type, "message": str(exc)},
        ) from exc

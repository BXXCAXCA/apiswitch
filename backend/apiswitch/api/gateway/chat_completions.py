from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db, require_gateway_token
from apiswitch.db.models import ApiToken
from apiswitch.gateway.errors import GatewayError
from apiswitch.gateway.executor import gateway_executor
from apiswitch.providers.base import ProviderError
from apiswitch.schemas.gateway import ChatCompletionRequest

router = APIRouter(prefix="/v1", tags=["Gateway - OpenAI Chat"])


@router.post("/chat/completions")
async def create_chat_completion(
    payload: ChatCompletionRequest,
    db: Session = Depends(get_db),
    api_token: ApiToken = Depends(require_gateway_token),
):
    try:
        if payload.stream:
            stream = await gateway_executor.stream_chat_completion(payload, db)
            return StreamingResponse(
                stream,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return await gateway_executor.execute_chat_completion(payload, db, api_token_id=api_token.id)
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

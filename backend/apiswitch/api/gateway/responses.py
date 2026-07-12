from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db, require_gateway_token
from apiswitch.db.models import ApiToken
from apiswitch.gateway.errors import GatewayError
from apiswitch.gateway.responses_executor import execute_responses, stream_responses
from apiswitch.providers.base import ProviderError
from apiswitch.schemas.gateway import ResponsesRequest
from apiswitch.services.routing_controls import validate_request_budget, validate_routing_tier

router = APIRouter(prefix="/v1", tags=["Gateway - OpenAI Responses"])


@router.post("/responses")
async def create_response(
    payload: ResponsesRequest,
    db: Session = Depends(get_db),
    api_token: ApiToken = Depends(require_gateway_token),
    session_key: str | None = Header(default=None, alias="X-APISwitch-Session"),
    routing_tier: str | None = Header(default=None, alias="X-APISwitch-Tier"),
    request_budget: float | None = Header(default=None, alias="X-APISwitch-Budget"),
) -> dict:
    try:
        tier = validate_routing_tier(routing_tier)
        budget = validate_request_budget(request_budget)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "invalid_routing_control", "message": str(exc)},
        ) from exc

    try:
        if payload.stream:
            stream = await stream_responses(
                payload,
                db,
                api_token_id=api_token.id,
                session_key=session_key,
                tier=tier,
                max_cost=budget,
            )
            return StreamingResponse(stream, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        return await execute_responses(
            payload,
            db,
            api_token_id=api_token.id,
            session_key=session_key,
            tier=tier,
            max_cost=budget,
        )
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

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db, require_gateway_token
from apiswitch.db.models import ApiToken, RequestLog
from apiswitch.gateway.errors import GatewayError
from apiswitch.gateway.executor import gateway_executor
from apiswitch.protocols.gemini_v1beta import chat_response_to_gemini, gemini_request_to_chat
from apiswitch.providers.base import ProviderError
from apiswitch.schemas.gateway import GeminiGenerateContentRequest
from apiswitch.services.routing_controls import validate_request_budget, validate_routing_tier

router = APIRouter(prefix="/v1beta", tags=["Gateway - Gemini v1beta"])


@router.post("/models/{model_name}:generateContent")
async def generate_content(
    model_name: str,
    payload: GeminiGenerateContentRequest,
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

    request = gemini_request_to_chat(model_name, payload)
    try:
        response = await gateway_executor.execute_chat_completion(
            request,
            db,
            api_token_id=api_token.id,
            session_key=session_key,
            tier=tier,
            max_cost=budget,
        )
        request_id = (response.get("apiswitch") or {}).get("request_id")
        if request_id:
            log = db.scalar(select(RequestLog).where(RequestLog.request_id == request_id))
            if log is not None:
                log.inbound_protocol = "gemini_v1beta"
                db.commit()
        return chat_response_to_gemini(response, model_name)
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

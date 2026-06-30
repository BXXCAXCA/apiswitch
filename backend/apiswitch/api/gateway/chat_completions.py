from fastapi import APIRouter

from apiswitch.gateway.executor import gateway_executor
from apiswitch.schemas.gateway import ChatCompletionRequest

router = APIRouter(prefix="/v1", tags=["Gateway - OpenAI Chat"])


@router.post("/chat/completions")
async def create_chat_completion(payload: ChatCompletionRequest) -> dict:
    return await gateway_executor.execute_chat_completion(payload)

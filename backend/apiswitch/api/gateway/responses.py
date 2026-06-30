from fastapi import APIRouter

from apiswitch.schemas.gateway import ResponsesRequest

router = APIRouter(prefix="/v1", tags=["Gateway - OpenAI Responses"])


@router.post("/responses")
async def create_response(payload: ResponsesRequest) -> dict:
    return {
        "id": "resp_mock_001",
        "object": "response",
        "model": payload.model,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Mock response from APISwitch Responses."}],
            }
        ],
    }

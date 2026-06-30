from apiswitch.schemas.gateway import ChatCompletionRequest, NormalizedRequest


def normalize_openai_chat(request: ChatCompletionRequest) -> NormalizedRequest:
    return NormalizedRequest(
        inbound_protocol="openai_chat",
        model=request.model,
        messages=request.messages,
        stream=request.stream,
        raw=request.model_dump(),
    )

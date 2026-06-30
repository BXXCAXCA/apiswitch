from apiswitch.providers.registry import provider_registry
from apiswitch.schemas.gateway import ChatCompletionRequest


class GatewayExecutor:
    async def execute_chat_completion(self, request: ChatCompletionRequest) -> dict:
        provider = provider_registry.get("mock")
        return await provider.chat(request)


gateway_executor = GatewayExecutor()

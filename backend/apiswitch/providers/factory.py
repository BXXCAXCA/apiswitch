from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, ProviderNode
from apiswitch.providers.anthropic import AnthropicProviderAdapter
from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.providers.compatible import CompatibleProviderAdapter
from apiswitch.providers.gemini import GeminiProviderAdapter
from apiswitch.providers.mock import MockProviderAdapter
from apiswitch.providers.openai import OpenAIProviderAdapter
from apiswitch.security.crypto import secret_crypto

OPENAI_COMPATIBLE_PROVIDER_TYPES = {
    "openrouter",
    "xai",
    "mistral",
    "deepseek",
    "groq",
    "together",
    "fireworks",
    "siliconflow",
    "dashscope",
    "zhipu",
    "moonshot",
    "volcengine",
    "minimax",
}


def _decrypt_api_key(provider: Provider, connection: ProviderConnection | None = None) -> str | None:
    encrypted = connection.credential_encrypted if connection and connection.credential_encrypted else provider.api_key_encrypted
    if not encrypted:
        return None
    return secret_crypto.decrypt(encrypted)


def build_provider_adapter(
    provider: Provider,
    connection: ProviderConnection | None = None,
    node: ProviderNode | None = None,
) -> ProviderAdapter:
    """Create an adapter for a legacy provider or a selected account/node target."""
    api_key = _decrypt_api_key(provider, connection)
    base_url = node.base_url if node is not None else provider.base_url
    if provider.type == "mock":
        return MockProviderAdapter()
    if provider.type == "openai":
        return OpenAIProviderAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    if provider.type == "anthropic":
        return AnthropicProviderAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    if provider.type == "gemini":
        return GeminiProviderAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    if provider.type == "compatible" or provider.type in OPENAI_COMPATIBLE_PROVIDER_TYPES:
        return CompatibleProviderAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    raise ProviderError(f"Provider type is not supported yet: {provider.type}", "unsupported_provider_type")


def build_selected_provider_adapter(db: Session, selected: object) -> ProviderAdapter:
    """Resolve a routed candidate's provider, credential and endpoint in one place."""
    provider_id = getattr(selected, "provider_id")
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise ProviderError(f"Provider config not found: {provider_id}", "provider_not_found")
    connection_id = getattr(selected, "provider_connection_id", None)
    node_id = getattr(selected, "provider_node_id", None)
    connection = db.get(ProviderConnection, connection_id) if connection_id is not None else None
    node = db.get(ProviderNode, node_id) if node_id is not None else None
    return build_provider_adapter(provider, connection=connection, node=node)

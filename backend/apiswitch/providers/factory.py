from apiswitch.db.models import Provider
from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.providers.compatible import CompatibleProviderAdapter
from apiswitch.providers.mock import MockProviderAdapter
from apiswitch.providers.openai import OpenAIProviderAdapter
from apiswitch.security.crypto import secret_crypto


def _decrypt_api_key(provider: Provider) -> str | None:
    if not provider.api_key_encrypted:
        return None
    return secret_crypto.decrypt(provider.api_key_encrypted)


def build_provider_adapter(provider: Provider) -> ProviderAdapter:
    api_key = _decrypt_api_key(provider)
    if provider.type == "mock":
        return MockProviderAdapter()
    if provider.type == "openai":
        return OpenAIProviderAdapter(
            base_url=provider.base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    if provider.type == "compatible":
        return CompatibleProviderAdapter(
            base_url=provider.base_url,
            api_key=api_key,
            timeout_seconds=provider.timeout_seconds,
        )
    raise ProviderError(f"Provider type is not supported yet: {provider.type}", "unsupported_provider_type")

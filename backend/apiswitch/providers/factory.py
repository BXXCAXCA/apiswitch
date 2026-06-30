from apiswitch.db.models import Provider
from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.providers.compatible import CompatibleProviderAdapter
from apiswitch.providers.mock import MockProviderAdapter


def build_provider_adapter(provider: Provider) -> ProviderAdapter:
    if provider.type == "mock":
        return MockProviderAdapter()
    if provider.type == "compatible":
        return CompatibleProviderAdapter(
            base_url=provider.base_url,
            api_key=None,
            timeout_seconds=provider.timeout_seconds,
        )
    raise ProviderError(f"Provider type is not supported yet: {provider.type}", "unsupported_provider_type")

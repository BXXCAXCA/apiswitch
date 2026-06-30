from apiswitch.providers.base import ProviderAdapter
from apiswitch.providers.mock import MockProviderAdapter


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}

    def register(self, key: str, provider: ProviderAdapter) -> None:
        self._providers[key] = provider

    def get(self, key: str) -> ProviderAdapter:
        return self._providers[key]

    def all(self) -> dict[str, ProviderAdapter]:
        return self._providers


provider_registry = ProviderRegistry()
provider_registry.register("mock", MockProviderAdapter())

"""AI provider registry for Buster OS."""

import logging
from typing import Optional

from buster.ai_providers.base import AIProvider


class ProviderNotFoundError(Exception):
    pass


class AIProviderRegistry:
    """Registers and resolves AI providers by name."""

    def __init__(self):
        self._providers: dict[str, AIProvider] = {}
        self._default: Optional[str] = None
        self.logger = logging.getLogger("buster.ai_providers.registry")

    def register(self, provider: AIProvider, default: bool = False) -> None:
        if provider.name in self._providers:
            raise ValueError(f"AI provider '{provider.name}' already registered")
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name
        self.logger.info("Registered AI provider '%s'", provider.name)

    def get(self, name: Optional[str] = None) -> AIProvider:
        resolved = name or self._default
        provider = self._providers.get(resolved)
        if provider is None:
            raise ProviderNotFoundError(f"Unknown AI provider '{resolved}'")
        return provider

    def names(self) -> list[str]:
        return sorted(self._providers.keys())

    def default(self) -> Optional[str]:
        return self._default

    def shutdown(self) -> None:
        self._providers.clear()
        self._default = None
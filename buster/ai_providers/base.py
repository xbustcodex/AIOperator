"""Base abstractions for AI providers."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

Role = str


class AIProviderError(Exception):
    pass


@dataclass
class AIMessage:
    role: Role
    content: str
    extra: dict = field(default_factory=dict)


@dataclass
class AICompletion:
    message: AIMessage
    model: str
    usage: dict = field(default_factory=dict)
    raw: Any = None


class AIProvider(ABC):
    """A pluggable interface to an AI backend (OpenAI-compatible API, local
    runner, etc.). Providers are registered with an AIProviderRegistry and
    addressed by name from agents and capabilities."""

    name: str = "base"

    def __init__(self, **options):
        self.options = options
        self.logger = logging.getLogger(f"buster.ai_providers.{self.name}")

    @abstractmethod
    def complete(self, messages: list[AIMessage], **kwargs) -> AICompletion:
        """Produce a completion for a conversation."""

    @abstractmethod
    def models(self) -> list[str]:
        """List models available through this provider."""
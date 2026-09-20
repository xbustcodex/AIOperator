"""Remote OpenAI-compatible provider using only the standard library."""

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from buster.ai_providers.base import AICompletion, AIMessage, AIProvider, AIProviderError


class RemoteProvider(AIProvider):
    """Talk to any OpenAI-compatible endpoint over HTTP (no external deps)."""

    name = "remote"

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1",
                 model: str = "", timeout: float = 30.0, **options):
        super().__init__(api_key=api_key, base_url=base_url, model=model, **options)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._model = model
        self.timeout = timeout
        self.logger.info("RemoteAI provider ready (base=%s model=%s)", base_url, model or "(server default)")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[AIMessage], **kwargs) -> AICompletion:
        if not self.api_key:
            raise AIProviderError("Remote API key not configured")

        model = kwargs.get("model") or self._model
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        for key in ("temperature", "max_tokens", "top_p"):
            if key in kwargs:
                payload[key] = kwargs[key]

        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise AIProviderError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise AIProviderError(f"Connection error: {exc.reason}") from exc

        choice = body["choices"][0]
        return AICompletion(
            message=AIMessage(role="assistant", content=choice["message"]["content"]),
            model=body.get("model", model),
            usage=body.get("usage", {}),
            raw=body,
        )

    def models(self) -> list[str]:
        if not self.api_key:
            return []
        request = urllib.request.Request(
            url=f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            return [entry.get("id") for entry in body.get("data", [])]
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
            return []
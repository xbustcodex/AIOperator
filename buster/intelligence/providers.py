"""AI-provider intelligence: availability, health and selection.

Buster stays local-first/offline-capable: providers are independent of the
basal nervous system and lifecycle. Provider failures degrade gracefully —
basic operation never depends on continuous cloud inference.
"""

import logging
import time

REMOTE_PROVIDER_NAME = "remote"


class ProviderIntelligence:
    """Health tracking and sensible provider selection."""

    def __init__(self, kernel):
        self.kernel = kernel
        self._remote_available: bool | None = None
        self._last_checked = 0.0
        self.logger = logging.getLogger("buster.intel.providers")

    # -- health --------------------------------------------------------

    def health(self) -> dict:
        registry = self.kernel.ai.providers
        names = registry.names()
        local_available = "local" in names or bool(names)
        remote_configured = False
        try:
            remote_configured = registry.get(REMOTE_PROVIDER_NAME).configured \
                if any(n == REMOTE_PROVIDER_NAME for n in names) else False
        except Exception:  # noqa: BLE001
            remote_configured = False

        # slow-but-graceful remote probe (bounded, cached)
        remote_available = False
        if remote_configured:
            remote_available = bool(self._probe_remote())

        return {
            "registered": names,
            "local_available": local_available,
            "remote_configured": remote_configured,
            "remote_available": remote_available,
            "offline_capable": local_available,
            "checked_at": self._last_checked,
        }

    def _probe_remote(self) -> bool:
        now = time.time()
        if now - self._last_checked < 60 and self._remote_available is not None:
            return self._remote_available
        self._last_checked = now
        try:
            provider = self.kernel.ai.providers.get("remote")
            models = provider.models()
            self._remote_available = bool(models) if models is not None else False
        except Exception:  # noqa: BLE001
            self._remote_available = False
        return bool(self._remote_available)

    # -- selection -------------------------------------------------------

    def select(self, goal: str = "", prefer: str | None = None) -> str:
        """Choose a provider; degrades from remote to local automatically."""
        if prefer and prefer in self.kernel.ai.providers.names():
            return prefer
        health = self.health()
        if health["remote_configured"] and health["remote_available"]:
            return REMOTE_PROVIDER_NAME
        if health["local_available"]:
            return "local"
        names = self.kernel.ai.providers.names()
        return names[0] if names else "local"

    def state(self) -> dict:
        return self.health()
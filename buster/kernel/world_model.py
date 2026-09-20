"""World model for Buster OS.

A structured, versioned snapshot of the environment the Buster instance is
running in: device state, workspace layout, active components and their
runtime health. Emitted as events whenever it changes.
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ComponentState:
    name: str
    status: str = "stopped"
    started_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class WorldModel:
    """Registry of known environment facts and component states."""

    def __init__(self, event_router=None):
        self._event_router = event_router
        self._facts: dict[str, Any] = {}
        self._components: dict[str, ComponentState] = {}
        self._version: int = 0
        self._updated_at: Optional[float] = None

    # -- facts ---------------------------------------------------------

    def set_fact(self, key: str, value: Any) -> None:
        self._facts[key] = value
        self._bump(f"fact.set.{key}")

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self._facts.get(key, default)

    def facts(self) -> dict:
        return dict(self._facts)

    # -- components ----------------------------------------------------

    def register_component(self, name: str, **metadata) -> ComponentState:
        state = ComponentState(name=name, metadata=metadata)
        self._components[name] = state
        self._bump(f"component.registered.{name}")
        return state

    def get_component(self, name: str) -> Optional[ComponentState]:
        return self._components.get(name)

    def component_status(self, name: str, status: str, **metadata) -> None:
        state = self._components.setdefault(name, ComponentState(name=name))
        state.status = status
        state.started_at = state.started_at if state.started_at is not None else time.time()
        state.metadata.update(metadata)
        self._bump(f"component.status.{name}")

    def components(self) -> list[dict]:
        return [asdict(c) for c in self._components.values()]

    # -- snapshot ------------------------------------------------------

    def snapshot(self) -> dict:
        snapshot = {
            "version": self._version,
            "updated_at": self._updated_at,
            "facts": self.facts(),
            "components": self.components(),
        }
        return snapshot

    def _bump(self, event_type: str) -> None:
        self._version += 1
        self._updated_at = time.time()
        if self._event_router is not None:
            self._event_router.emit(event_type, {"world": self.snapshot()})
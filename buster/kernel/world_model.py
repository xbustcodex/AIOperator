"""World model for Buster OS.

A structured, versioned snapshot of the environment the Buster instance is
running in: device state, workspace layout, active components, runtime health,
known entities, and a bounded history of meaningful events.

Facts distinguish *observed* facts (provenance from perception/sensors/events)
from *inferred* facts (hypotheses carrying confidence). The event history is a
bounded ring buffer so the model never becomes an uncontrolled dump.
"""

import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ComponentState:
    name: str
    status: str = "stopped"
    started_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class WorldModel:
    """Registry of known facts, components, entities and recent events."""

    def __init__(self, event_router=None, history_limit: int = 100):
        self._event_router = event_router
        self._facts: dict[str, Any] = {}
        self._observed: dict[str, dict] = {}
        self._inferred: dict[str, dict] = {}
        self._components: dict[str, ComponentState] = {}
        self._entities: dict[str, dict] = {}
        self._events: deque = deque(maxlen=history_limit)
        self._version: int = 0
        self._updated_at: Optional[float] = None

    # -- raw facts (compat) ----------------------------------------------

    def set_fact(self, key: str, value: Any) -> None:
        self._facts[key] = value
        self._bump(f"fact.set.{key}")

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self._facts.get(key, default)

    def facts(self) -> dict:
        return dict(self._facts)

    # -- observed vs inferred facts ----------------------------------------

    def observe(self, key: str, value: Any, source: str = "perception",
                provenance: str = "observed") -> None:
        """Record a directly observed fact (sensor/event/validated action)."""
        self._observed[key] = {
            "value": _serializable(value),
            "source": source,
            "provenance": provenance,
            "ts": time.time(),
        }
        self.set_fact(key, value)

    def infer(self, key: str, value: Any, confidence: float = 0.5,
              source: str = "reasoning") -> None:
        """Record an inferred fact carrying confidence."""
        self._inferred[key] = {
            "value": _serializable(value),
            "confidence": min(max(float(confidence), 0.0), 1.0),
            "source": source,
            "ts": time.time(),
        }
        self.set_fact(key, value)

    def observed_facts(self) -> dict:
        return {k: dict(v) for k, v in self._observed.items()}

    def inferred_facts(self) -> dict:
        return {k: dict(v) for k, v in self._inferred.items()}

    def forget_inferred(self, key: str) -> None:
        self._inferred.pop(key, None)

    # -- entities -----------------------------------------------------------

    def add_entity(self, entity_id: str, kind: str, attrs: Optional[dict] = None) -> None:
        existing = self._entities.get(entity_id)
        if existing is None:
            self._entities[entity_id] = {
                "id": entity_id, "kind": kind, "attrs": dict(attrs or {}),
                "created": time.time(), "updated": time.time(),
            }
        else:
            existing["attrs"].update(attrs or {})
            existing["updated"] = time.time()
        self._bump(f"entity.{entity_id}")

    def entities(self, kind: Optional[str] = None) -> list[dict]:
        items = [e for e in self._entities.values()
                 if kind is None or e["kind"] == kind]
        return items

    # -- bounded event history ------------------------------------------------

    def record_event(self, event_type: str, detail: Optional[dict] = None) -> None:
        """Record a meaningful event (bounded ring buffer, deduped by type+detail)."""
        entry = {"ts": time.time(), "type": event_type, "detail": dict(detail or {})}
        if self._events and self._events[-1]["type"] == event_type and \
                self._events[-1]["detail"] == entry["detail"]:
            return  # suppress adjacent noise
        self._events.append(entry)
        self._bump(f"event.{event_type}")

    def recent_events(self, limit: int = 20, kinds: Optional[tuple] = None) -> list[dict]:
        items = list(self._events)
        if kinds:
            items = [e for e in items if e["type"] in kinds]
        return items[-limit:]

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
            "observed": self.observed_facts(),
            "inferred": self.inferred_facts(),
            "entities": self.entities(),
            "events": self.recent_events(20),
            "components": self.components(),
        }
        return snapshot

    def _bump(self, event_type: str) -> None:
        self._version += 1
        self._updated_at = time.time()
        if self._event_router is not None:
            self._event_router.emit(event_type, {"world": self.snapshot()})


def _serializable(value):
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    return str(value)
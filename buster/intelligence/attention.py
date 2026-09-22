"""Attention for Buster OS.

Prioritizes what deserves processing. Routine sensor noise is suppressed;
meaningful changes are scored by relevance, urgency, novelty, goal alignment
and resource state, then surfaced as attention notes through the event bus.
"""

import logging
import time
from dataclasses import dataclass, field

from buster.intelligence.rhythm import Rhythm

ROUTINE_KINDS = {"host", "battery"}


@dataclass
class AttentionNote:
    kind: str
    level: str
    message: str
    score: float = 0.0
    ts: float = field(default_factory=time.time)
    details: dict = field(default_factory=dict)


class Attention:
    """Bounded, priority-ordered attention queue."""

    def __init__(self, kernel, capacity: int = 32):
        self.kernel = kernel
        self.capacity = capacity
        self._queue: list[AttentionNote] = []
        self._seen_messages: set[str] = set()
        self.logger = logging.getLogger("buster.intel.attention")

    # -- scoring ---------------------------------------------------------

    def score(self, kind: str, level: str, message: str,
              goals: list[str] | None = None, rhythm: Rhythm = Rhythm.IDLE) -> float:
        weight = {"critical": 4.0, "warning": 3.0, "info": 1.5,
                  "ok": 0.5, "debug": 0.1}.get(level, 0.5)
        novelty = 0.0 if message in self._seen_messages else 2.0
        relevance = 0.0
        needle = message.lower()
        for goal in (goals or []):
            if any(word in needle for word in str(goal).lower().split()):
                relevance = 1.0
                break
        routine = 0.0
        if kind in ROUTINE_KINDS and level in ("info", "ok"):
            routine = -2.0
        rhythm_penalty = -2.0 if rhythm in (Rhythm.SLEEP,) else \
            (-1.0 if rhythm in (Rhythm.CONSTRAINED,) else 0.0)
        return weight + novelty + relevance + routine + rhythm_penalty

    # -- ingest ----------------------------------------------------------

    def note_signal(self, kind: str, level: str, message: str,
                    goals: list[str] | None = None,
                    rhythm: Rhythm = Rhythm.IDLE, details: dict | None = None) -> AttentionNote | None:
        score = self.score(kind, level, message, goals, rhythm)
        if score < 1.5:
            return None  # suppressed as routine noise
        note = AttentionNote(kind=kind, level=level, message=message,
                             score=score, details=details or {})
        self._seen_messages.add(message)
        self._queue.append(note)
        self._queue.sort(key=lambda n: n.score, reverse=True)
        if len(self._queue) > self.capacity:
            self._queue = self._queue[: self.capacity]
        self._emit(note)
        return note

    def note_event(self, event_type: str, payload: dict) -> AttentionNote | None:
        kind = event_type
        level = payload.get("level", "info")
        message = payload.get("message") or event_type
        return self.note_signal(kind, level, message,
                                details=payload.get("details"))

    # -- introspection -----------------------------------------------------

    def peek(self, limit: int = 10) -> list[AttentionNote]:
        return self._queue[:limit]

    def consume(self, limit: int = 8) -> list[AttentionNote]:
        consumed = self._queue[:limit]
        self._queue = self._queue[limit:]
        return consumed

    def clear(self) -> None:
        self._queue.clear()

    def state(self) -> dict:
        return {"pending": [{"kind": n.kind, "level": n.level,
                             "message": n.message, "score": round(n.score, 2),
                             "ts": n.ts} for n in self._queue[:12]],
                "capacity": self.capacity}

    def _emit(self, note: AttentionNote) -> None:
        if self.kernel is not None and getattr(self.kernel, "event_router", None) is not None \
                and self.kernel.event_router.running:
            self.kernel.event_router.emit("attention.note", {
                "kind": note.kind, "level": note.level, "message": note.message,
                "score": round(note.score, 2),
            })
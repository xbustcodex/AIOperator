"""Central event bus for Buster OS.

Supports synchronous and asynchronous dispatch of events across the whole
system. All subsystems communicate exclusively through this router so that
there is exactly one event graph and one source of truth.
"""

import logging
import queue
import threading
from typing import Callable, Dict, List

#: Callable contract for event handlers: receives the event payload dict.
EventHandler = Callable[[dict], None]

#: Sentinel pushed to the queue on shutdown.
_STOP_SENTINEL = None


class EventRouter:
    """Thread-safe event bus with a single background dispatch loop."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._event_queue: "queue.Queue" = queue.Queue()
        self._running = False
        self._lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self.logger = logging.getLogger("buster.kernel.event_router")

    def start(self) -> None:
        """Start the dispatch loop. Idempotent."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._event_loop, name="event-router", daemon=True
        )
        self._worker_thread.start()
        self.logger.info("EventRouter started.")

    def stop(self) -> None:
        """Stop the dispatch loop and drain pending events."""
        if not self._running:
            return
        self._running = False
        self._event_queue.put(_STOP_SENTINEL)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
        self.logger.info("EventRouter stopped.")

    @property
    def running(self) -> bool:
        return self._running

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)
        self.logger.debug("Handler subscribed to event '%s'", event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
                self.logger.debug("Handler unsubscribed from event '%s'", event_type)

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        """Queue an event for asynchronous handling by the dispatch loop."""
        if not self._running:
            self.logger.warning("emit() called while EventRouter is stopped; dropping event '%s'", event_type)
            return
        event = {"type": event_type, "payload": payload if payload is not None else {}}
        self._event_queue.put(event)
        self.logger.debug("Event '%s' emitted", event_type)

    def emit_sync(self, event_type: str, payload: dict | None = None) -> list:
        """Dispatch directly to handlers on the calling thread.

        Returns a list of exceptions raised by handlers (all handlers still
        run so that one faulty subscriber cannot starve the others).
        """
        payload = payload if payload is not None else {}
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
        errors = []
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:  # noqa: BLE001 - never break the bus on handler failure
                self.logger.exception("Handler error for event '%s'", event_type)
                errors.append(exc)
        return errors

    def _event_loop(self) -> None:
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if event is None:
                break
            event_type, payload = event.get("type"), event.get("payload")
            with self._lock:
                handlers = list(self._subscribers.get(event_type, []))
            for handler in handlers:
                try:
                    handler(payload)
                except Exception:  # noqa: BLE001
                    self.logger.exception("Error in event handler for '%s'", event_type)
        self.logger.info("Event dispatch loop stopped.")
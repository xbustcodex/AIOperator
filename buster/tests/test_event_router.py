"""Unit tests for the central EventRouter."""

import threading
import time
import unittest

from buster.kernel.event_router import EventRouter


class EventRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = EventRouter()
        self.router.start()

    def tearDown(self):
        self.router.stop()

    def test_async_dispatch(self):
        received = []
        self.router.subscribe("test.event", lambda p: received.append(p))
        self.router.emit("test.event", {"a": 1})
        deadline = time.time() + 2
        while not received and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(received, [{"a": 1}])

    def test_sync_dispatch(self):
        received = []
        self.router.subscribe("sync.event", lambda p: received.append(p))
        self.router.emit_sync("sync.event", {"x": 2})
        self.assertEqual(received, [{"x": 2}])

    def test_unsubscribe(self):
        received = []
        handler = lambda p: received.append(p)
        self.router.subscribe("u.event", handler)
        self.router.unsubscribe("u.event", handler)
        errors = self.router.emit_sync("u.event", {})
        self.assertEqual(errors, [])
        self.assertEqual(received, [])

    def test_handler_error_does_not_block_others(self):
        received = []

        def boom(payload):
            raise ValueError("boom")

        self.router.subscribe("err.event", boom)
        self.router.subscribe("err.event", lambda p: received.append(p))
        errors = self.router.emit_sync("err.event", {})
        self.assertEqual(len(errors), 1)
        self.assertEqual(received, [{}])


if __name__ == "__main__":
    unittest.main()
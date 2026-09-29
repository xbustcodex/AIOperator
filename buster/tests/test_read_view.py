"""Phase 5B.1 -- the complete typed ``read(view)`` path.

Exercises the whole chain against a REAL runtime:

    Buster APK -> TerminalP -> PRootDistro -> buster exec.py -> intel view

Each view must come back as a structured ``buster.view/1`` document produced by
Buster's own bounded view authority, and every hostile form must be refused at
parse time, before the install path is resolved or the runtime is touched.
"""

import io
import json
import os
import tempfile
import unittest
from unittest import mock

from buster import exec as bexec
from buster.exec import exec_main
from buster.config import Config
from buster.kernel.core import Kernel
from buster.runtime import RuntimeServer

VIEWS = ("goals", "memory", "attention", "activity", "device", "settings",
         "jobs")


def _run(args):
    out = io.StringIO()
    code = exec_main(args, out=out)
    return code, out.getvalue()


class ReadViewDispatchTests(unittest.TestCase):
    """Every declared view resolves; nothing else can be named."""

    def test_every_view_is_accepted_by_the_parser(self):
        for view in VIEWS:
            self.assertIn(view, bexec.READ_VIEWS, view)

    def test_the_vocabulary_is_exactly_eleven_operations(self):
        self.assertEqual(len(bexec.ALL_VERBS), 11)
        for verb in ("status", "services", "capabilities", "health", "ping",
                     "present", "deployment", "read", "service-start",
                     "service-restart", "service-status"):
            self.assertIn(verb, bexec.ALL_VERBS, verb)

    def test_invalid_view_is_refused(self):
        for bad in ("secrets", "MEMORY", "goals;id", "", "a b"):
            code, _ = _run(["read", bad])
            self.assertEqual(code, 2, bad)

    def test_traversal_string_is_refused(self):
        for bad in ("../etc/passwd", "/etc/passwd", "../../root/.buster",
                    "core/../../etc/shadow"):
            code, _ = _run(["read", bad])
            self.assertEqual(code, 2, bad)

    def test_missing_view_is_refused(self):
        code, _ = _run(["read"])
        self.assertEqual(code, 2)

    def test_extra_argument_is_refused(self):
        for bad in (["read", "goals", "memory"], ["read", "goals", "x"]):
            code, _ = _run(bad)
            self.assertEqual(code, 2)

    def test_refusals_never_touch_the_runtime(self):
        # Arity and view are checked before the install path is resolved, so a
        # hostile value cannot cause a runtime call.
        with mock.patch.object(bexec, "_client",
                               side_effect=AssertionError("runtime touched")):
            for bad in (["read"], ["read", "../etc/passwd"],
                        ["read", "goals", "extra"]):
                code, _ = _run(bad)
                self.assertEqual(code, 2)


class ReadViewRuntimeTests(unittest.TestCase):
    """Each view returns a structured document from the real runtime."""

    @classmethod
    def setUpClass(cls):
        cls.install = tempfile.mkdtemp()
        config = Config(config_path=os.path.join(cls.install, "config.json"))
        config.set("install_path", cls.install + os.sep)
        cls.kernel = Kernel(config=config)
        cls.server = RuntimeServer(cls.kernel, cls.install)
        if not cls.server.start():
            raise RuntimeError("test runtime could not acquire its lock")
        for action in ("time.now",):
            cls.kernel.permissions.grant(action)
        # The exec layer resolves its own install; point it at this runtime so
        # the read path is exercised end to end rather than mocked.
        cls._previous_install = os.environ.get("BUSTER_INSTALL")
        os.environ["BUSTER_INSTALL"] = cls.install
        import threading
        threading.Thread(target=cls.server.serve, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_install is None:
            os.environ.pop("BUSTER_INSTALL", None)
        else:
            os.environ["BUSTER_INSTALL"] = cls._previous_install
        try:
            from buster.runtime import RuntimeClient, wait_offline
            RuntimeClient(cls.install).rpc("shutdown")
            wait_offline(cls.install, timeout=10)
        except Exception:
            pass
        finally:
            cls.server.close()

    def _read(self, view):
        code, raw = _run(["read", view])
        self.assertEqual(code, 0, raw)
        doc = json.loads(raw)
        self.assertTrue(doc["ok"], doc)
        self.assertEqual(doc["verb"], "read")
        self.assertEqual(doc["view"], view)
        return doc

    def test_read_goals(self):
        doc = self._read("goals")
        self.assertEqual(doc["schema"], "buster.view/1")
        self.assertIn("data", doc)

    def test_read_memory(self):
        self.assertIn("data", self._read("memory"))

    def test_read_attention(self):
        self.assertIn("data", self._read("attention"))

    def test_read_activity(self):
        self.assertIn("data", self._read("activity"))

    def test_read_device(self):
        self.assertIn("data", self._read("device"))

    def test_read_settings(self):
        self.assertIn("data", self._read("settings"))

    def test_read_jobs(self):
        self.assertIn("data", self._read("jobs"))

    def test_every_view_is_structured_with_the_schema(self):
        for view in VIEWS:
            with self.subTest(view=view):
                self.assertEqual(self._read(view)["schema"], "buster.view/1")

    def test_read_goes_through_busters_own_view_authority(self):
        # The runtime must interpret the view; the exec layer must not read
        # any state file itself.
        self._read("memory")
        # The document must be produced by the runtime, not by the exec layer
        # reading a state file: an offline runtime yields a typed error, not data.
        with mock.patch.object(bexec, "_client", return_value=(None, None)):
            code, raw = _run(["read", "memory"])
        self.assertFalse(json.loads(raw)["ok"])
        self.assertNotIn("data", json.loads(raw))

    def test_deployment_reports_the_running_runtime(self):
        code, raw = _run(["deployment"])
        self.assertEqual(code, 0, raw)
        doc = json.loads(raw)
        self.assertTrue(doc["ok"], doc)
        self.assertTrue(doc["deployed"])
        self.assertEqual(doc["runtimeState"], "running")
        self.assertEqual(doc["version"], bexec.get_version())
        # No filesystem path is disclosed.
        self.assertNotIn("path", doc)
        self.assertNotIn("install_path", doc)

    def test_existing_operations_are_unchanged(self):
        for verb in ("ping", "health", "status", "services", "capabilities",
                     "present"):
            code, raw = _run([verb])
            self.assertEqual(code, 0, verb)
            self.assertTrue(json.loads(raw)["ok"], verb)

    def test_service_control_is_unchanged(self):
        # Unchanged semantics: a name the catalog does not have yields a
        # typed refusal rather than an error or a success.
        code, raw = _run(["service-status", "buster-runtime"])
        self.assertEqual(code, 1, raw)
        doc = json.loads(raw)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["verb"], "service-status")
        self.assertIn("unknown service", doc["error"])


class ReadResultBoundTests(unittest.TestCase):
    """Structured, bounded results -- never a raw stream, never a partial one."""

    def test_result_carries_only_bounded_typed_fields(self):
        # Without a runtime the result is a typed refusal. It must never be a
        # partial success, and must carry no data payload.
        code, raw = _run(["read", "goals"])
        self.assertEqual(code, 0)
        doc = json.loads(raw)
        self.assertEqual(set(doc), {"verb", "ok", "view", "error"})
        self.assertFalse(doc["ok"])
        self.assertNotIn("data", doc)

    def test_offline_read_fails_closed_with_a_typed_error(self):
        # With no runtime reachable the result is typed, never an empty success.
        with mock.patch.object(bexec, "_client", return_value=(None, None)):
            code, raw = _run(["read", "memory"])
        self.assertEqual(code, 0)
        doc = json.loads(raw)
        self.assertFalse(doc["ok"])
        self.assertIn("error", doc)
        self.assertNotIn("data", doc)


if __name__ == "__main__":
    unittest.main()

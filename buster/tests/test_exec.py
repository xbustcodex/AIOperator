"""Typed ``buster exec`` bridge contract tests.

Covers BOTH sides of the guest boundary:

* the closed verb vocabulary (every expected verb dispatches, unknown verbs
  fail, missing/excess arguments fail),
* the mirrored service-name grammar (authoritative
  ``^[A-Za-z0-9][A-Za-z0-9_.-]*$`` with the 64-character ceiling): valid edge
  cases reach their handler, every invalid form is refused BEFORE any runtime
  access, and shell/metacharacter strings never become executable input.

The exec surface is a client of the single runtime: these tests never
construct a second Kernel for control-path assertions; daemon interaction is
exercised through the file-RPC server the runtime tests already use.
"""

import io
import json
import os
import tempfile
import unittest
from unittest import mock

from buster import exec as bexec
from buster.exec import exec_main, is_valid_service_name


def _run(args):
    out = io.StringIO()
    code = exec_main(args, out=out)
    return code, out.getvalue()


def _json_out(stdout):
    return json.loads(stdout)


# -- closed vocabulary ---------------------------------------------------------

class ExecVocabularyTests(unittest.TestCase):
    def test_every_read_verb_dispatches_offline(self):
        for verb in bexec.READ_VERBS:
            code, stdout = _run([verb])
            self.assertEqual(code, 0, verb)
            doc = _json_out(stdout)
            self.assertEqual(doc["verb"], verb)
            self.assertTrue(doc["ok"])
            self.assertFalse(doc["online"])  # no daemon in this environment

    def test_ping_document(self):
        code, stdout = _run(["ping"])
        self.assertEqual(code, 0)
        doc = _json_out(stdout)
        self.assertTrue(doc["pong"])
        self.assertTrue(doc["version"])

    def test_status_document_carries_heartbeat_when_offline(self):
        install = tempfile.mkdtemp()
        state = os.path.join(install, "state")
        os.makedirs(state)
        with open(os.path.join(state, "runtime.status.json"), "w",
                  encoding="utf-8") as handle:
            handle.write('{"state": "stale-but-read"}')
        with mock.patch.object(bexec, "_install", return_value=install):
            code, stdout = _run(["status"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertFalse(doc["online"])
        self.assertEqual(doc["heartbeat"]["state"], "stale-but-read")

    def test_unknown_verbs_fail_without_runtime_access(self):
        for argv in ([], ["exec"], ["start"], ["shell"], ["run", "ls"],
                     ["/bin/sh"], ["-c", "echo unsafe"], ["status", "x"],
                     ["service-start"], ["service-start", "a", "b"],
                     ["service-status"], ["SERVICE-START", "x"]):
            code, _ = _run(argv)
            self.assertEqual(code, 2, argv)

    def test_rejected_args_never_touch_the_runtime(self):
        with mock.patch.object(bexec, "_client",
                               side_effect=AssertionError("runtime touched")):
            for argv in ([], ["nope"], ["service-start"], ["status", "--x"]):
                code, _ = _run(argv)
                self.assertEqual(code, 2, argv)


# -- mirrored service-name grammar ---------------------------------------------

VALID_NAMES = (
    "runtime", "RUNTIME", "runtime--id", "event.router_1", "1service",
    "buster-runtime", "a", "x" * 64, "R2D2.C-3PO_v9",
)

INVALID_NAMES = (
    "", "-runtime", ".runtime", "../runtime", "/runtime", "runtime/child",
    "runtime id", "runtime;id", "runtime|id", "runtime&", "runtime`id`",
    "runtime$(id)", "runtime\nid", "runtime\\child", "runtime;rm -rf /",
    "x" * 65, "café", "runtime\tx", None, 42, ["runtime"],
)


class ServiceNameGrammarTests(unittest.TestCase):
    def test_valid_edge_cases_are_accepted(self):
        for name in VALID_NAMES:
            self.assertTrue(is_valid_service_name(name), name)

    def test_invalid_forms_are_rejected(self):
        for name in INVALID_NAMES:
            self.assertFalse(is_valid_service_name(name), repr(name))

    def test_invalid_names_never_reach_the_runtime(self):
        with mock.patch.object(bexec, "_client",
                               side_effect=AssertionError("runtime touched")):
            for name in INVALID_NAMES:
                if name is None:
                    continue
                code, _ = _run(["service-start", name])
                self.assertEqual(code, 2, repr(name))
                code, _ = _run(["service-status", name])
                self.assertEqual(code, 2, repr(name))

    def test_grammar_matches_the_host_bridge_literal(self):
        self.assertEqual(bexec.SERVICE_NAME.pattern,
                         r"[A-Za-z0-9][A-Za-z0-9_.-]*")
        self.assertEqual(bexec.SERVICE_NAME_MAX, 64)


# -- daemon-backed service catalog (single-runtime, file RPC) ------------------

def _bootstrapped():
    install = tempfile.mkdtemp()
    from buster.config import Config
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    from buster.bootstrap import bootstrap_offline
    bootstrap_offline(config, install_path=install)
    return install, config


def _serve(install, config):
    import threading
    from buster.kernel.core import Kernel
    from buster.runtime import RuntimeServer
    kernel = Kernel(config=config)
    server = RuntimeServer(kernel, install)
    assert server.start(), "server could not acquire lock"
    threading.Thread(target=server.serve, daemon=True).start()
    return server, kernel


class ExecServiceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.install, self.config = _bootstrapped()
        self.server, self.kernel = _serve(self.install, self.config)
        patcher = mock.patch.object(bexec, "_install",
                                    return_value=self.install)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.server.close()

    def _run(self, args):
        out = io.StringIO()
        code = exec_main(args, out=out)
        return code, out.getvalue()

    def test_services_document_lists_kernel_components(self):
        code, stdout = self._run(["services"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertTrue(doc["online"])
        names = {row["name"] for row in doc["services"]}
        self.assertIn("event-router", names)
        self.assertIn("scheduler", names)

    def test_service_status_of_kernel_component(self):
        code, stdout = self._run(["service-status", "event-router"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(doc["service"]["kind"], "kernel")
        self.assertEqual(doc["service"]["state"], "running")

    def test_unknown_service_status_is_a_typed_error(self):
        code, stdout = self._run(["service-status", "no-such-thing"])
        doc = _json_out(stdout)
        self.assertEqual(code, 1)
        self.assertFalse(doc["ok"])
        self.assertIn("unknown service", doc["error"])

    def test_service_start_kernel_component_is_reported_not_changed(self):
        code, stdout = self._run(["service-start", "scheduler"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertTrue(doc["ok"])
        self.assertFalse(doc["changed"])
        self.assertIn("kernel-managed", doc["detail"])

    def test_agent_service_lifecycle_over_rpc(self):
        self.kernel.agent_manager.spawn("runtime--id")
        code, stdout = self._run(["service-status", "runtime--id"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(doc["service"]["kind"], "agent")

        code, stdout = self._run(["service-start", "runtime--id"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertTrue(doc["changed"])

        code, stdout = self._run(["service-restart", "runtime--id"])
        doc = _json_out(stdout)
        self.assertEqual(code, 0)
        self.assertTrue(doc["ok"])

    def test_metacharacter_names_are_refused_before_the_daemon(self):
        server = self.server
        for name in ("runtime;id", "runtime$(id)", "-runtime", "x" * 65):
            code, _ = self._run(["service-start", name])
            self.assertEqual(code, 2, name)
        # nothing was dispatched to the daemon for those inputs
        self.assertTrue(server.lock.is_online())


if __name__ == "__main__":
    unittest.main()

"""The ``buster exec`` operation vocabulary must agree across all three layers.

The closed vocabulary is a three-way contract:

1. the Buster OS guest parser (``buster/exec.py``),
2. the proot-distro host dispatcher that launches the guest,
3. the authenticated TerminalP bridge registry (and the AIDL it exposes).

A mismatch would mean the host forwarding a verb the guest refuses, or the
bridge advertising an operation no guest implements. This test reads each
layer's source and asserts the sets are identical.

The sibling repositories are not present in every checkout (a Buster-only
clone, a CI runner, a packaged source tree), so the cross-repository
assertions skip rather than fail when a layer is absent. The guest-side
assertion is unconditional.
"""

import ast
import os
import re
import unittest

from buster import exec as bexec

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_NEIGHBOURS = os.path.dirname(_REPO)


def _terminalp_root() -> str:
    """The authoritative TerminalP checkout.

    TerminalP's working checkout is D:/workSpace/TerminalP. A sibling copy
    also exists beside this repository, but it is a STALE branch of the same
    upstream, so reading it would assert against code that predates the
    principal registry. Prefer the authoritative path, fall back to the
    sibling only when it is absent.
    """
    authoritative = r"D:\workSpace\TerminalP"
    if os.path.isdir(authoritative):
        return authoritative
    return os.path.join(_NEIGHBOURS, "TerminalP")


_TERMINALP = _terminalp_root()
_PROOT = os.path.join(_NEIGHBOURS, "TerminalP-PRootDistro", "proot_distro",
                      "commands", "buster.py")
_REGISTRY = os.path.join(
    _TERMINALP, "app", "src", "main", "java", "com", "termux",
    "app", "privilege", "OperationRegistry.java")
_TERMINALP_AIDL = os.path.join(
    _TERMINALP, "app", "src", "main", "aidl", "com", "primetech",
    "terminal", "buster", "IBusterBridge.aidl")
_PTT_AIDL = os.path.join(
    _NEIGHBOURS, "PrimeTech_Terminal", "app", "src", "main", "aidl", "com",
    "primetech", "terminal", "buster", "IBusterBridge.aidl")

EXPECTED_VERBS = {
    "status", "services", "capabilities", "health", "ping",
    "service-start", "service-restart", "service-status", "present",
    # 5B.1: the read-only integration.
    "deployment", "read",
}

AIDL_METHOD_FOR_VERB = {
    "status": "busterStatus", "services": "busterServices",
    "capabilities": "busterCapabilities", "health": "busterHealth",
    "ping": "busterPing", "service-start": "busterServiceStart",
    "service-restart": "busterServiceRestart",
    "service-status": "busterServiceStatus", "present": "busterPresent",
    "deployment": "busterDeployment", "read": "busterRead",
}


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class GuestVocabularyTests(unittest.TestCase):
    """The guest parser is the authority and is always present."""

    def test_vocabulary_is_the_eleven_typed_operations(self):
        self.assertEqual(set(bexec.ALL_VERBS), EXPECTED_VERBS)
        # Nine accepted operations plus read(view), added in 5B.1.
        self.assertEqual(len(bexec.ALL_VERBS), 11)

    def test_present_carries_no_target(self):
        # Argument-free by construction: nothing about a presentation target
        # is expressible in the guest half of the contract.
        self.assertIn("present", bexec._READ_DOCS)
        self.assertNotIn("present", bexec.SERVICE_VERBS)


class HostDispatcherVocabularyTests(unittest.TestCase):
    """proot-distro must forward exactly the guest's vocabulary."""

    def setUp(self):
        if not os.path.isfile(_PROOT):
            self.skipTest("proot-distro checkout is not present")

    def _sets(self):
        tree = ast.parse(_read(_PROOT))
        found = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id in ("_EXEC_OPERATIONS", "_SERVICE_OPERATIONS",
                              "_VIEW_OPERATIONS"):
                found[target.id] = set(ast.literal_eval(node.value.args[0]))
        return found

    def test_allowed_vocabulary_matches_the_guest(self):
        found = self._sets()
        host = (found["_EXEC_OPERATIONS"] | found["_SERVICE_OPERATIONS"]
                | found.get("_VIEW_OPERATIONS", set()))
        self.assertEqual(host, EXPECTED_VERBS)
        self.assertEqual(host, set(bexec.ALL_VERBS))
        # The two sets stay disjoint, so no verb is reachable both ways.
        self.assertFalse(found["_EXEC_OPERATIONS"] & found["_SERVICE_OPERATIONS"])

    def test_present_has_no_argument_bearing_variant(self):
        # `_exec_inner` accepts a token only when the list is exactly one long,
        # so no `present <url>` form can be constructed.
        found = self._sets()
        self.assertIn("present", found["_EXEC_OPERATIONS"])
        self.assertNotIn("present", found["_SERVICE_OPERATIONS"])
        for variant in ("present-url", "present-open-url", "present-target"):
            self.assertNotIn(variant, found["_EXEC_OPERATIONS"])
            self.assertNotIn(variant, found["_SERVICE_OPERATIONS"])


class TerminalPBridgeVocabularyTests(unittest.TestCase):
    """The authenticated bridge must expose exactly the same operations."""

    def setUp(self):
        if not os.path.isfile(_REGISTRY):
            self.skipTest("TerminalP checkout is not present")

    def test_guest_operation_map_matches(self):
        text = _read(_REGISTRY)
        start = text.index("static {")
        end = text.index("BUSTER_GUEST_OPERATIONS =", start)
        mapped = set(re.findall(
            r'guest\.put\(OP_BUSTER_\w+,\s*"([^"]+)"\)', text[start:end]))
        self.assertEqual(mapped, EXPECTED_VERBS)
        self.assertEqual(mapped, set(bexec.ALL_VERBS))

    def test_present_is_not_a_service_operation(self):
        # `present` takes no service name, so it must not be resolvable with
        # one; the registry refuses a non-null serviceName for it.
        text = _read(_REGISTRY)
        body = text[text.index("public static boolean isBusterServiceOperation"):
                    text.index("@Nullable", text.index("public static boolean isBusterServiceOperation"))]
        self.assertNotIn("OP_BUSTER_PRESENT", body)
        resolve = text[text.index("public OperationSpec resolveBuster"):
                       text.index("private OperationSpec busterSpec")]
        # Anything that is not a service operation must reject a service name.
        self.assertIn("if (serviceName != null)", resolve)
        self.assertIn("return null", resolve)

    def test_aidl_exposes_present_with_no_target_parameter(self):
        text = _read(_TERMINALP_AIDL)
        methods = set(re.findall(r"void\s+(buster\w+)\s*\(", text))
        self.assertEqual(methods, set(AIDL_METHOD_FOR_VERB.values()))
        # present(correlationId, callback) only -- no url, package or intent.
        self.assertRegex(
            text, r"void\s+busterPresent\(in String correlationId,\s*"
                   r"IBusterBridgeCallback callback\);")
        for forbidden in ("busterPresentUrl", "busterPresentIntent", "busterOpen"):
            self.assertNotIn(forbidden, text)


class PrimeTechTerminalAidlTests(unittest.TestCase):
    """The client copy of the AIDL must not drift from the host's."""

    def setUp(self):
        if not os.path.isfile(_PTT_AIDL):
            self.skipTest("PrimeTech Terminal checkout is not present")

    def test_client_aidl_matches_the_host_aidl(self):
        if not os.path.isfile(_TERMINALP_AIDL):
            self.skipTest("TerminalP checkout is not present")
        host = set(re.findall(r"void\s+(buster\w+)\s*\(", _read(_TERMINALP_AIDL)))
        client = set(re.findall(r"void\s+(buster\w+)\s*\(", _read(_PTT_AIDL)))
        self.assertEqual(client, host)
        self.assertIn("busterPresent", client)


if __name__ == "__main__":
    unittest.main()

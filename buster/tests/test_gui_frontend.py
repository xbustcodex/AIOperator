"""Buster GUI frontend routing tests, run as part of the Python test suite.

The regression these cover is client-side: on a fresh install ``app.js``
redirected to ``#/onboarding`` while ``onboarding`` was not a resolvable route,
so the redirect fell back to Home, re-ran the guard, assigned a hash the
document already had (no ``hashchange``), and the app sat in its
"Starting…/Waking Buster…" markup forever.

The assertions live in ``buster/tests/gui_frontend/run.mjs`` because they
exercise the real ES modules. This module exists so the established gate

    python -m unittest discover -s buster/tests -p "test_*.py"

keeps covering them. Node is required; the test skips (rather than silently
passing) when Node is unavailable.
"""

import os
import shutil
import subprocess
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNNER = os.path.join(_HERE, "gui_frontend", "run.mjs")


class GuiFrontendRoutingTests(unittest.TestCase):
    """The consumer UI must leave its loading state on a fresh install."""

    def test_frontend_routing_regressions_pass(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required to run the GUI frontend tests")
        self.assertTrue(os.path.isfile(_RUNNER),
                        f"frontend test runner missing: {_RUNNER}")
        completed = subprocess.run(
            [node, _RUNNER],
            cwd=os.path.dirname(_HERE), capture_output=True, text=True,
            timeout=180,
        )
        self.assertEqual(
            completed.returncode, 0,
            "GUI frontend routing regressions failed:\n"
            f"{completed.stdout}\n{completed.stderr}")


if __name__ == "__main__":
    unittest.main()

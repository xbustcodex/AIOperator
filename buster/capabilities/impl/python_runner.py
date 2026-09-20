"""Python execution capability with a restricted namespace.

Runs code inside a sandbox dict without ``__builtins__.__import__``
executed against the interpreter's own shell; a basic blocklist guards the
most dangerous builtins.
"""

import io
import sys
import traceback

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult

_BLOCKED = {"__import__", "open", "exec", "eval", "compile", "input"}

if isinstance(__builtins__, dict):
    _BUILTINS_DICT = __builtins__
else:
    _BUILTINS_DICT = getattr(__builtins__, "__dict__", {})

_SAFE_BUILTINS = {
    name: value for name, value in _BUILTINS_DICT.items()
    if name not in _BLOCKED
}


class PythonRunnerCapability(Capability):
    """Execute Python expressions / code in a jailed namespace."""

    name = "python"
    actions_list = ["python.eval", "python.exec", "python.version"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "python.version":
            return CapabilityResult.ok(sys.version)

        code = extra.get("code")
        if not code:
            return CapabilityResult.fail("Missing 'code'")

        namespace = {"__builtins__": dict(_SAFE_BUILTINS), "_result": None}
        namespace.update(extra.get("env", {}))

        stdout = io.StringIO()
        old_stdout, sys.stdout = sys.stdout, stdout
        try:
            if ctx.action == "python.eval":
                namespace["_result"] = eval(code, namespace, namespace)
            else:
                exec(compile(code, "<buster>", "exec"), namespace, namespace)
        except Exception:  # noqa: BLE001 - report richly, never crash the bus
            return CapabilityResult.fail(traceback.format_exc())
        finally:
            sys.stdout = old_stdout

        return CapabilityResult.ok({
            "result": namespace.get("_result"),
            "stdout": stdout.getvalue(),
            "vars": {k: v for k, v in namespace.items() if not k.startswith("__")},
        })
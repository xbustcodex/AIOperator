"""Typed ``buster exec`` surface for the TerminalP privileged bridge.

The TerminalP privileged bridge dispatches a fixed set of Buster operations
through ``proot-distro buster exec <verb> [<service-name>]``. This module is
the guest-side half of that contract:

* a CLOSED vocabulary of operations (never a generic command passthrough),
* the service-name grammar mirrored from the host bridge
  (``^[A-Za-z0-9][A-Za-z0-9_.-]*$``, 1..64 characters),
* exactly one JSON document on stdout per invocation,
* typed exit codes: 0 = document produced / control succeeded,
  1 = refused or failed (document still explains why), 2 = usage/grammar.

There is deliberately NO fallback here: no shell evaluation, no arbitrary
argv forwarding, no executable path input, no caller-controlled environment
or working directory, and no generic command mode. Unknown operations and
malformed service names are rejected at parse time, before any runtime is
touched. A refused name never reaches the runtime.

Runtime mapping (single-runtime invariant: this CLI is a client, never a
second Kernel):

* ``status`` / ``ping`` / ``capabilities`` / ``services`` / ``health`` are
  read-only diagnostics and produce a document even when the runtime is
  offline (``"online": false``), because a state report is a successful
  diagnostic. Control verbs refuse while offline with a typed error.
* ``service-start`` / ``service-restart`` / ``service-status`` operate on the
  runtime service catalog served by the daemon over its file RPC: kernel
  components (``event-router``, ``scheduler``), named agents and named
  scheduler jobs. Kernel components are observed only -- they start and stop
  with the runtime. Agent ``spawn``/``activate``/``stop`` are registry
  lifecycle events inside the one kernel, never code execution.
* ``present`` asks the host to show the Buster interface. It is
  argument-free and names no target: the guest reports only that its own
  runtime is serving the local loopback UI, and TerminalP -- the sole
  Android/elevation broker -- constructs the bounded presentation action. The
  guest can therefore never direct the host to open an arbitrary URL,
  package, activity or Intent string. A document is produced even when the
  runtime is offline, with ``"ready": false`` and the reason.
"""

import json
import re
import sys

from buster.version import get_version

# Mirror of TerminalP OperationRegistry.SERVICE_NAME / PrimeTech Terminal
# BusterBridge.BusterServiceName. Keep the three grammars identical.
SERVICE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
SERVICE_NAME_MAX = 64
SERVICE_NAME_MIN = 1

READ_VERBS = ("status", "services", "capabilities", "health", "ping")
SERVICE_VERBS = ("service-start", "service-restart", "service-status")
#: ``present`` asks the authenticated TerminalP bridge to show the Buster GUI
#: on Android. It takes no argument and names no target: the guest reports
#: only what its own runtime is serving, and TerminalP -- the sole
#: Android/elevation broker -- constructs the bounded presentation action.
PRESENT_VERB = "present"
#: ``deployment`` reports the identity of the Buster runtime currently serving
#: this install, so the authenticated caller can tell what is actually
#: deployed. Read-only: it never installs, updates, starts or stops anything.
DEPLOYMENT_VERB = "deployment"
#: ``read(view)`` returns ONE bounded informational view drawn from a closed
#: enum. There is no arbitrary view string, path, URL, query language or
#: command form: the view is resolved against the set below and nothing the
#: caller supplies can name a module, function or file.
READ_VERB = "read"
READ_VIEWS = ("goals", "memory", "attention", "activity", "device",
              "settings", "jobs")
ALL_VERBS = READ_VERBS + SERVICE_VERBS + (PRESENT_VERB, DEPLOYMENT_VERB,
                                         READ_VERB)

_RPC_TIMEOUT = 10.0


def is_valid_service_name(name) -> bool:
    """Mirror of the authoritative host bridge service-name grammar."""
    if not isinstance(name, str):
        return False
    if not (SERVICE_NAME_MIN <= len(name) <= SERVICE_NAME_MAX):
        return False
    return SERVICE_NAME.fullmatch(name) is not None


def _install():
    from buster.install import resolve_install_path
    return resolve_install_path()


def _heartbeat(install):
    """Last daemon heartbeat, or None. Read-only."""
    import os
    try:
        path = os.path.join(install, "state", "runtime.status.json")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _client(install):
    """Live RuntimeClient + RemoteKernel facade, or (None, None) when offline."""
    from buster.runtime import RuntimeClient
    client = RuntimeClient(install, timeout=_RPC_TIMEOUT)
    if not client.is_online():
        return None, None
    from buster.runtime import RemoteKernel
    return client, RemoteKernel(client)


def _emit(out, document):
    out.write(json.dumps(document, indent=2, sort_keys=True, default=str) + "\n")


def _usage(out, message):
    print(f"[ERROR] {message}", file=sys.stderr)
    print("Usage: buster exec <operation>", file=sys.stderr)
    print("  read:    " + ", ".join(READ_VERBS), file=sys.stderr)
    print("  service: " + ", ".join(f"{v} <name>" for v in SERVICE_VERBS),
          file=sys.stderr)
    print("  present: " + PRESENT_VERB + "  (no arguments)", file=sys.stderr)
    print("  deployment: " + DEPLOYMENT_VERB + "  (no arguments)", file=sys.stderr)
    print("  read <view>: one of " + ", ".join(_READ_VIEWS), file=sys.stderr)
    return 2


def _error(out, verb, message, code=1):
    _emit(out, {"verb": verb, "ok": False, "error": message})
    return code


# -- read verbs ---------------------------------------------------------------

def _doc_ping(install, client, remote):
    return {"verb": "ping", "ok": True, "pong": True,
            "version": get_version(), "online": client is not None}


def _doc_status(install, client, remote):
    if client is None:
        return {"verb": "status", "ok": True, "online": False,
                "version": get_version(), "runtime": None,
                "heartbeat": _heartbeat(install)}
    return {"verb": "status", "ok": True, "online": True,
            "version": get_version(), "runtime": remote.status()}


def _doc_services(install, client, remote):
    if client is None:
        return {"verb": "services", "ok": True, "online": False,
                "version": get_version(), "services": []}
    rows = client.rpc("services")["data"]["services"]
    return {"verb": "services", "ok": True, "online": True,
            "version": get_version(), "services": rows}


def _doc_capabilities(install, client, remote):
    if client is None:
        return {"verb": "capabilities", "ok": True, "online": False,
                "version": get_version(), "capabilities": [], "actions": [],
                "error": "runtime offline"}
    doc = {"verb": "capabilities", "ok": True, "online": True,
           "version": get_version()}
    doc.update(client.rpc("caps")["data"])
    return doc


def _doc_health(install, client, remote):
    from buster.diagnostics.doctor import run_doctor, run_os_doctor
    checks = list(run_doctor().checks) + list(run_os_doctor().checks)
    return {"verb": "health", "ok": True, "online": client is not None,
            "version": get_version(), "checks": checks,
            "failed": sum(1 for c in checks if not c["ok"])}


def _doc_present(install, client, remote):
    """Report the GUI presentation request for the host bridge to act on.

    The guest contributes no target. It names no URL, package, activity,
    action or Intent string, and accepts no argument: it only states that the
    Buster runtime is serving its local interface, and TerminalP -- the sole
    Android/elevation broker -- decides what to present and how. A document
    that reaches a host that does not implement ``present`` is still valid
    and harmless; it simply describes readiness.
    """
    doc = {"verb": "present", "ok": True, "version": get_version(),
           "install_path": install, "online": client is not None,
           "ready": False, "url": None, "error": None}
    if client is None:
        doc["error"] = "runtime offline; run 'buster start' first"
        return doc
    from buster.runtime import RuntimeOfflineError, RuntimeRpcError
    try:
        status = remote.status()
    except (RuntimeOfflineError, RuntimeRpcError) as exc:
        doc["error"] = f"{type(exc).__name__}: {exc}"
        return doc
    state = status.get("state")
    doc["runtime_state"] = state
    if state != "running":
        doc["error"] = f"runtime state is {state!r}"
        return doc
    # The interface address is derived from Buster's own launch state, never
    # from caller input, and is loopback-only: the guest cannot ask the host
    # to present anything that is not this runtime's own local UI.
    from buster.launch import DEFAULT_GUI_PORT
    doc["ready"] = True
    doc["url"] = f"http://127.0.0.1:{DEFAULT_GUI_PORT}"
    return doc


def _doc_deployment(install, client, remote):
    """Identity of the Buster runtime currently serving this install.

    Read-only, and deliberately free of filesystem paths: the caller learns
    which runtime is deployed, not where it lives on disk.
    """
    from buster.runtime import RuntimeOfflineError, RuntimeRpcError
    doc = {"verb": DEPLOYMENT_VERB, "ok": True,
           "version": get_version(),
           "deploymentFormatVersion": "1",
           "runtimeState": "unknown",
           "bridgeContractVersion": "11",
           "compatibility": "unknown"}
    if client is None:
        doc["deployed"] = False
        doc["error"] = "runtime offline; run 'buster start' first"
        return doc
    try:
        status = remote.status()
    except (RuntimeOfflineError, RuntimeRpcError) as exc:
        doc["deployed"] = False
        doc["error"] = f"{type(exc).__name__}: {exc}"
        return doc
    state = status.get("state")
    doc["deployed"] = True
    doc["runtimeState"] = state or "unknown"
    doc["compatibility"] = "current"
    return doc


#: The closed view set each maps onto a bounded Buster-owned read. No entry
#: names a file, a module or a caller-supplied expression.
_READ_VIEWS = ("goals", "memory", "attention", "activity", "device",
                "settings", "jobs")


def _doc_read(install, client, remote, view):
    """One bounded informational view from Buster's own intel layer.

    Busters own capability and permission model remains the inner authority:
    this delegates to the runtime's existing view surface rather than reading
    any file directly.
    """
    from buster.runtime import RuntimeOfflineError, RuntimeRpcError
    if view not in _READ_VIEWS:
        return {"verb": READ_VERB, "ok": False,
                "error": f"unknown view: {view!r}",
                "available": list(_READ_VIEWS)}
    if client is None:
        return {"verb": READ_VERB, "ok": False, "view": view,
                "error": "runtime offline; run 'buster start' first"}
    try:
        document = remote.intel_view(view)
    except (RuntimeOfflineError, RuntimeRpcError) as exc:
        return {"verb": READ_VERB, "ok": False, "view": view,
                "error": f"{type(exc).__name__}: {exc}"}
    return {"verb": READ_VERB, "ok": True, "view": view,
            "schema": "buster.view/1", "data": document}


_READ_DOCS = {
    "ping": _doc_ping,
    "status": _doc_status,
    "services": _doc_services,
    "capabilities": _doc_capabilities,
    "health": _doc_health,
    "present": _doc_present,
    "deployment": _doc_deployment,
}


# -- service control verbs ----------------------------------------------------

def _ctl_service(verb, name, out, install=None):
    install = install or _install()
    client, remote = _client(install)
    if client is None:
        return _error(out, verb, "runtime offline; run 'buster start' first")

    try:
        if verb == "service-status":
            rows = client.rpc("services")["data"]["services"]
            row = next((r for r in rows if r["name"] == name), None)
            if row is None:
                return _error(out, verb, f"unknown service '{name}'")
            _emit(out, {"verb": verb, "ok": True, "name": name, "service": row})
            return 0

        response = client.rpc("service_start" if verb == "service-start"
                              else "service_restart", name=name)
    except Exception as exc:  # noqa: BLE001 - typed failure, never a crash
        return _error(out, verb, f"{type(exc).__name__}: {exc}")

    if not response.get("ok"):
        return _error(out, verb, response.get("error", "service op failed"))
    _emit(out, dict(response["data"], verb=verb, ok=True, name=name))
    return 0


# -- entry point --------------------------------------------------------------

def exec_main(args, out=None) -> int:
    """Dispatch one typed ``buster exec`` invocation. Returns the exit code."""
    out = out if out is not None else sys.stdout
    args = list(args)
    if not args:
        return _usage(out, "buster exec requires a supported operation")
    verb, rest = args[0], args[1:]

    if verb in SERVICE_VERBS:
        if len(rest) != 1:
            return _usage(out, f"buster {verb} requires exactly one service name")
        name = rest[0]
        if not is_valid_service_name(name):
            return _usage(out, f"invalid service name: {name!r}")
        return _ctl_service(verb, name, out)

    if verb == READ_VERB:
        # Exactly one argument, drawn from the closed view set. Anything else
        # is refused before the install path is resolved or the runtime is
        # touched, so no arbitrary string can reach the guest.
        if len(rest) != 1:
            return _usage(out, f"buster {verb} requires exactly one view")
        view = rest[0]
        if view not in _READ_VIEWS:
            return _usage(out, f"unknown view: {view!r}; "
                               f"expected one of {', '.join(_READ_VIEWS)}")
        try:
            install = _install()
            client, remote = _client(install)
            _emit(out, _doc_read(install, client, remote, view))
            return 0
        except Exception as exc:  # noqa: BLE001 - typed failure, never a crash
            return _error(out, verb, f"{type(exc).__name__}: {exc}")

    if verb in READ_VERBS or verb in (PRESENT_VERB, DEPLOYMENT_VERB):
        # `present` is argument-free by construction: arity is checked here,
        # before any install path is resolved or runtime is touched, so a
        # caller-supplied URL/path/argv can never reach the bridge.
        if rest:
            return _usage(out, f"buster {verb} takes no arguments")
        try:
            install = _install()
            client, remote = _client(install)
            _emit(out, _READ_DOCS[verb](install, client, remote))
            return 0
        except Exception as exc:  # noqa: BLE001 - report, never crash the bridge
            return _error(out, verb, f"{type(exc).__name__}: {exc}")

    return _usage(out, f"unknown exec operation: {verb!r}")

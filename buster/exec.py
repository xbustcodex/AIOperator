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
ALL_VERBS = READ_VERBS + SERVICE_VERBS

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


_READ_DOCS = {
    "ping": _doc_ping,
    "status": _doc_status,
    "services": _doc_services,
    "capabilities": _doc_capabilities,
    "health": _doc_health,
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

    if verb in READ_VERBS:
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

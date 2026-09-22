"""Console commands for the Buster CLI.

Lifecycle (single-runtime discipline):
    buster bootstrap   offline install/init (never boots a Kernel)
    buster start       bring the single runtime online (daemon)
    buster status      read runtime lock + heartbeat (no local Kernel)
    buster shell       interactive shell attached to the live runtime
    buster stop        shut the live runtime down

Management commands route through RPC when a runtime is online, otherwise
fall back to a transient kernel that boots, acts and shuts down.
"""

import json
import os
import sys
import time

from buster.config import Config
from buster.version import get_version

DEFAULT_INSTALL = os.path.expanduser("~/.buster/")


# --------------------------------------------------------------------------
# install-path resolution
# --------------------------------------------------------------------------


def _install_path(args) -> str:
    for i, arg in enumerate(args):
        if arg == "--install-path" and i + 1 < len(args):
            return args[i + 1]
    return Config().get("install_path", DEFAULT_INSTALL)


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------


def cmd_bootstrap(args) -> int:
    install = _install_path(args)
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    from buster.bootstrap import bootstrap_offline
    summary = bootstrap_offline(config, install_path=install)
    print(f"Buster OS {summary['version']} bootstrap complete.")
    print(f"  install:   {summary['install_path']}")
    print(f"  layout:    {summary['layout_created'] or '(already present)'}")
    print(f"  first_run: {summary['first_run']}")
    return 0


def cmd_daemon(args) -> int:
    from buster.runtime import run_daemon
    return run_daemon(_install_path(args))


def cmd_start(args) -> int:
    from buster.runtime import RuntimeLock, spawn_daemon, wait_online
    install = _install_path(args)
    if RuntimeLock(install).is_online():
        print("[ERROR] a Buster runtime is already online.", file=sys.stderr)
        print("        Refusing to create a competing runtime.", file=sys.stderr)
        return 1
    spawn_daemon(install)
    if not wait_online(install):
        print("[ERROR] runtime did not come online.", file=sys.stderr)
        return 1
    info = RuntimeLock(install).read() or {}
    print(f"Buster runtime online (pid {info.get('pid')}).")
    print("Run 'buster status', 'buster shell' or 'buster stop'.")
    return 0


def cmd_status(args) -> int:
    from buster.runtime import RuntimeLock
    install = _install_path(args)
    lock = RuntimeLock(install)
    info = lock.read()
    online = lock.is_online()
    print(f"State:     {'running' if online else 'offline'}")
    if info:
        print(f"PID:       {info.get('pid')}")
        print(f"Since:     {time.ctime(info.get('at', 0))}")
    if not online:
        return 1
    heartbeat = _read_heartbeat(install)
    if heartbeat:
        print(f"Version:   {heartbeat.get('version', '?')}")
        print(f"Kernel:    {heartbeat.get('state', '?')}")
        print(f"EventBus:  {'running' if heartbeat.get('event_router_running') else 'stopped'}")
        print(f"Scheduler: {'running' if heartbeat.get('scheduler_running') else 'stopped'}")
        print(f"Capabil. : {', '.join(heartbeat.get('capabilities', [])) or 'none'}")
        print(f"Providers: {', '.join(heartbeat.get('ai_providers', [])) or 'none'}")
    return 0


def cmd_shell(args) -> int:
    from buster.runtime import RuntimeClient, RemoteKernel, RuntimeOfflineError
    from buster.shell.session import InteractiveShell
    install = _install_path(args)
    client = RuntimeClient(install)
    if not client.is_online():
        print("[ERROR] no runtime online. Run 'buster start' first.", file=sys.stderr)
        return 1
    return InteractiveShell(kernel=RemoteKernel(client)).repl()


def cmd_stop(args) -> int:
    from buster.runtime import RuntimeClient, RuntimeOfflineError, wait_offline
    install = _install_path(args)
    client = RuntimeClient(install)
    if not client.is_online():
        print("Runtime already offline.")
        return 0
    try:
        client.rpc("shutdown")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] send stop failed: {exc}", file=sys.stderr)
        return 1
    if not wait_offline(install):
        print("[ERROR] runtime did not stop cleanly.", file=sys.stderr)
        return 1
    print("Buster runtime stopped cleanly.")
    return 0


def _read_heartbeat(install: str) -> dict | None:
    import json as _json
    path = os.path.join(install, "state", "runtime.status.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _json.load(handle)
    except (OSError, ValueError):
        return None


def cmd_version(args) -> int:
    print(get_version())
    return 0


def cmd_doctor(args) -> int:
    from buster.diagnostics.doctor import run_doctor
    report = run_doctor()
    print(f"{'Check':<22} {'Status':<7} Detail")
    print("-" * 60)
    for check in report.checks:
        state = "PASS" if check["ok"] else "FAIL"
        print(f"{check['name']:<22} {state:<7} {check['detail']}")
    print("-" * 60)
    if report.failed:
        print(f"{report.failed} check(s) failed.")
        return 1
    print("All checks passed.")
    return 0


# --------------------------------------------------------------------------
# management (RPC-first, transient-kernel fallback)
# --------------------------------------------------------------------------


def _client_or_kernel(install: str):
    """Resolve an execution target: RPC remote or a transient local kernel."""
    from buster.runtime import RuntimeClient
    client = RuntimeClient(install)
    if client.is_online():
        from buster.runtime import RemoteKernel
        return RemoteKernel(client), None
    config = Config(config_path=os.path.join(install, "config", "config.json"))
    from buster.kernel.core import Kernel
    kernel = Kernel(config=config)
    return None, kernel


def cmd_caps(args) -> int:
    install = _install_path(args)
    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        capabilities = remote.cap.list_capabilities()
        actions = remote.cap.list_actions()
    else:
        kernel.start()
        try:
            capabilities = kernel.cap.list_capabilities()
            actions = kernel.cap.list_actions()
        finally:
            kernel.stop()

    for name in capabilities:
        print(name)
    print()
    print("Actions:")
    for action in actions:
        print(f"  {action}")
    return 0


def cmd_grant(args) -> int:
    if not args:
        print("[ERROR] usage: buster grant <action> [--install-path <dir>]", file=sys.stderr)
        return 2
    install = _install_path(args)
    action = args[0]
    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        remote.permissions.grant(action)
    else:
        kernel.permissions.grant(action)
    print(f"granted: {action}")
    return 0


def cmd_deny(args) -> int:
    if not args:
        print("[ERROR] usage: buster deny <action> [--install-path <dir>]", file=sys.stderr)
        return 2
    install = _install_path(args)
    action = args[0]
    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        remote.permissions.deny(action)
    else:
        kernel.permissions.deny(action)
    print(f"denied: {action}")
    return 0


def cmd_run(args) -> int:
    if not args:
        print("[ERROR] usage: buster run <action> [k=v ...] [--install-path <dir>]", file=sys.stderr)
        return 2
    install = _install_path(args)
    action = args[0]
    params = {}
    for arg in args[1:]:
        if "=" in arg:
            key, _, value = arg.partition("=")
            params[key] = _coerce(value)

    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        result = remote.cap.call(action, extra=params,
                                 context={"actor": "cli", "source": "cli"})
    else:
        kernel.start()
        try:
            result = kernel.cap.call(action, extra=params,
                                     context={"actor": "cli", "source": "cli"})
        finally:
            kernel.stop()

    if not result.success:
        print(f"[{action}] {result.error}", file=sys.stderr)
        return 1
    if result.data is not None:
        print(json.dumps(result.data, default=str, indent=2))
    else:
        print("OK")
    return 0


def cmd_config(args) -> int:
    config = Config(config_path=os.path.join(_install_path(args), "config", "config.json"))
    if not args:
        print(json.dumps(config.all(), indent=2))
        return 0
    if len(args) == 1:
        value = config.get_nested(args[0])
        print(value if value is not None else "(unset)")
        return 0
    key, value = args[0], args[1]
    config.set_nested(key, _coerce(value))
    print(f"set: {key} = {config.get_nested(key)}")
    return 0


def cmd_jobs(args) -> int:
    install = _install_path(args)
    remote, kernel = _client_or_kernel(install)
    if args and args[0] == "cancel":
        job_id = args[1] if len(args) > 1 else ""
        cancelled = (remote.scheduler.cancel(job_id) if remote is not None
                     else kernel.scheduler.cancel(job_id))
        print(f"cancelled: {job_id}" if cancelled else f"[ERROR] no pending job '{job_id}'")
        return 0 if cancelled else 1

    jobs = (remote.scheduler.list_jobs() if remote is not None
            else kernel.scheduler.list_jobs())
    if not jobs:
        print("no jobs scheduled")
        return 0
    for job in jobs:
        kind = "periodic" if job.periodic else "one-shot"
        print(f"{job.id[:8]}  {job.status.value:<10} {job.name:<24} {kind}")
    return 0


def cmd_audit(args) -> int:
    import time as _time
    install = _install_path(args)
    limit = int(args[0]) if args and args[0].isdigit() else 10
    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        entries = remote.audit.tail(limit)
    else:
        from buster.kernel.audit import Audit
        audit = Audit(os.path.join(install, "logs"))
        entries = audit.tail(limit)
    for entry in entries:
        stamp = _time.strftime("%Y-%m-%d %H:%M:%S",
                               _time.localtime(entry["ts"]))
        print(f"{stamp}  {entry['action']:<28} actor={entry.get('actor', '')}")
    return 0


def cmd_intel(args) -> int:
    section = args[0] if args else "health"
    install = _install_path(args)
    remote, kernel = _client_or_kernel(install)
    if remote is not None:
        view = remote.intel_view(section)
    else:
        from buster.kernel.core import Kernel
        kernel = Kernel(config=Config(config_path=os.path.join(install, "config", "config.json")))
        view = kernel.intel_view(section)
    print(json.dumps(view, default=str, indent=2))
    return 0


def cmd_goal(args) -> int:
    install = _install_path(args)
    text_args = [a for a in args if not a.startswith("--install-path")]
    while "--install-path" in text_args:
        idx = text_args.index("--install-path")
        text_args = text_args[:idx] + text_args[idx + 2:]
    remote, kernel = _client_or_kernel(install)
    if not text_args:
        if remote is not None:
            view = remote.intel_view("goals")
        else:
            from buster.kernel.core import Kernel
            kernel = Kernel(config=Config(config_path=os.path.join(install, "config", "config.json")))
            view = kernel.intel_view("goals")
        print(json.dumps(view, default=str, indent=2))
        return 0
    goal = " ".join(text_args)
    if remote is not None:
        result = remote.process_goal(goal)
    else:
        from buster.kernel.core import Kernel
        kernel = Kernel(config=Config(config_path=os.path.join(install, "config", "config.json")))
        kernel.start()
        try:
            result = kernel.process_goal(goal)
        finally:
            kernel.stop()
    print(json.dumps(result, default=str, indent=2))
    return 0


def cmd_health(args) -> int:
    return cmd_intel(["health", *_install_flag(args)])


def _install_flag(args):
    for i, arg in enumerate(args):
        if arg == "--install-path" and i + 1 < len(args):
            return [arg, args[i + 1]]
    return []


def cmd_help(args) -> int:
    print(
        "Buster OS - AI-native phone node for TerminalP\n"
        "\n"
        "Usage: buster <command> [options]\n"
        "\n"
        "Lifecycle (single runtime):\n"
        "  bootstrap          Offline install/init (never boots a kernel)\n"
        "  start              Bring the single runtime online (daemon)\n"
        "  status             Report runtime state (lock + heartbeat)\n"
        "  shell              Attach an interactive shell to the runtime\n"
        "  stop               Shut the runtime down cleanly\n"
        "\n"
        "Diagnostics:\n"
        "  doctor             Run environment health checks\n"
        "  version            Print the installed version\n"
        "\n"
        "Management (RPC-first, transient fallback):\n"
        "  caps               List capabilities and actions\n"
        "  run <action>       Invoke a capability action (k=v args)\n"
        "  grant <action>     Grant an action permission\n"
        "  deny <action>      Deny an action permission\n"
        "  config [key]       Read or set configuration\n"
        "  jobs [cancel <id>] List / cancel scheduler jobs\n"
        "  audit [limit]      Show audit trail\n"
        "  help               Show this help\n"
        "\n"
        "Options:\n"
        "  --install-path <dir>  Override the install directory\n"
    )
    return 0


def _coerce(value: str):
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


COMMANDS = {
    "bootstrap": cmd_bootstrap,
    "start": cmd_start,
    "status": cmd_status,
    "shell": cmd_shell,
    "stop": cmd_stop,
    "daemon": cmd_daemon,
    "doctor": cmd_doctor,
    "version": cmd_version,
    "caps": cmd_caps,
    "grant": cmd_grant,
    "deny": cmd_deny,
    "run": cmd_run,
    "config": cmd_config,
    "jobs": cmd_jobs,
    "audit": cmd_audit,
    "intel": cmd_intel,
    "goal": cmd_goal,
    "health": cmd_health,
    "help": cmd_help,
}


def dispatch_command(command: str, args) -> int:
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"[ERROR] Unknown command '{command}'", file=sys.stderr)
        cmd_help(args)
        return 2
    return handler(args)
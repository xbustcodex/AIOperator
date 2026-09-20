"""Console commands for the Buster CLI."""

import json
import os
import sys

from buster.config import Config
from buster.kernel.core import Kernel
from buster.version import get_version


def _instance() -> Kernel:
    return Kernel(config=Config())


def cmd_start(args) -> int:
    kernel = _instance()
    kernel.start()
    print(f"Buster OS kernel {get_version()} started.")
    print(f"  state:        {kernel.status()['state']}")
    print(f"  capabilities: {', '.join(kernel.cap.list_capabilities())}")
    return 0


def cmd_status(args) -> int:
    kernel = _instance()
    status = kernel.status()
    print(f"State:     {status['state']}")
    print(f"Version:   {status['version']}")
    print(f"EventBus:  {'running' if status['event_router_running'] else 'stopped'}")
    print(f"Scheduler: {'running' if status['scheduler_running'] else 'stopped'}")
    print(f"Providers: {', '.join(status['ai_providers'])}")
    print(f"Capabil. : {', '.join(status['capabilities']) or 'none'}")
    print(f"Agents:    {', '.join(status['agents']) or 'none'}")
    print(f"Jobs:      {len(status['jobs'])}")
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


def cmd_version(args) -> int:
    print(get_version())
    return 0


def cmd_shell(args) -> int:
    from buster.shell.session import InteractiveShell
    kernel = _instance()
    kernel.start()
    try:
        shell = InteractiveShell(kernel=kernel)
        return shell.repl()
    finally:
        kernel.stop()


def cmd_caps(args) -> int:
    kernel = _instance()
    for name in kernel.cap.list_capabilities():
        print(name)
    print()
    print("Actions:")
    for action in kernel.cap.list_actions():
        print(f"  {action}")
    return 0


def cmd_grant(args) -> int:
    if not args:
        print("[ERROR] usage: buster grant <action>", file=sys.stderr)
        return 2
    kernel = _instance()
    action = args[0]
    kernel.permissions.grant(action)
    print(f"granted: {action}")
    return 0


def cmd_deny(args) -> int:
    if not args:
        print("[ERROR] usage: buster deny <action>", file=sys.stderr)
        return 2
    kernel = _instance()
    action = args[0]
    kernel.permissions.deny(action)
    print(f"denied: {action}")
    return 0


def cmd_run(args) -> int:
    if not args:
        print("[ERROR] usage: buster run <action> [k=v ...]", file=sys.stderr)
        return 2
    kernel = _instance()
    kernel.start()
    action = args[0]
    params = {}
    for arg in args[1:]:
        if "=" in arg:
            key, _, value = arg.partition("=")
            params[key] = _coerce(value)
    result = kernel.cap.call(action, extra=params, context={"actor": "cli", "source": "cli"})
    if not result.success:
        print(f"[{action}] {result.error}", file=sys.stderr)
        kernel.stop()
        return 1
    if result.data is not None:
        print(json.dumps(result.data, default=str, indent=2))
    else:
        print("OK")
    kernel.stop()
    return 0


def cmd_config(args) -> int:
    config = Config()
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
    kernel = _instance()
    scheduler = kernel.scheduler
    if args and args[0] == "cancel":
        job_id = args[1] if len(args) > 1 else ""
        if scheduler.cancel(job_id):
            print(f"cancelled: {job_id}")
            return 0
        print(f"[ERROR] no pending job '{job_id}'", file=sys.stderr)
        return 1
    jobs = scheduler.list_jobs()
    if not jobs:
        print("no jobs scheduled")
        return 0
    for job in jobs:
        kind = "periodic" if job.periodic else "one-shot"
        print(f"{job.id[:8]}  {job.status.value:<10} {job.name:<24} {kind}")
    return 0


def cmd_audit(args) -> int:
    import time
    from buster.config import Config as Cfg
    install_path = Cfg().get("install_path", os.path.expanduser("~/.buster/"))
    from buster.kernel.audit import Audit
    audit = Audit(os.path.join(install_path, "logs"))
    limit = int(args[0]) if args and args[0].isdigit() else 10
    for entry in audit.tail(limit):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["ts"]))
        print(f"{stamp}  {entry['action']:<28} actor={entry.get('actor', '')}")
    return 0


def cmd_help(args) -> int:
    print(
        "Buster OS - AI-native environment for Termux\n"
        "\n"
        "Usage: buster <command> [options]\n"
        "\n"
        "Commands:\n"
        "  start              Start the Buster kernel\n"
        "  status             Show kernel status\n"
        "  doctor             Run environment health checks\n"
        "  version            Print the installed version\n"
        "  shell              Launch the interactive shell\n"
        "  caps               List capabilities and actions\n"
        "  run <action>       Invoke a capability action (k=v args)\n"
        "  grant <action>     Grant an action permission\n"
        "  deny <action>      Deny an action permission\n"
        "  config [key]       Read or set configuration\n"
        "  jobs [cancel <id>] List / cancel scheduler jobs\n"
        "  audit [limit]      Show audit trail\n"
        "  help               Show this help\n"
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
    "start": cmd_start,
    "status": cmd_status,
    "doctor": cmd_doctor,
    "version": cmd_version,
    "shell": cmd_shell,
    "caps": cmd_caps,
    "grant": cmd_grant,
    "deny": cmd_deny,
    "run": cmd_run,
    "config": cmd_config,
    "jobs": cmd_jobs,
    "audit": cmd_audit,
    "help": cmd_help,
}


def dispatch_command(command: str, args) -> int:
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"[ERROR] Unknown command '{command}'", file=sys.stderr)
        cmd_help(args)
        return 2
    return handler(args)
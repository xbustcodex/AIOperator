"""Console commands for the Buster CLI."""

import sys
from buster.config import Config
from buster.kernel.core import Kernel
from buster.version import get_version


def cmd_start(args) -> int:
    kernel = Kernel(config=Config())
    kernel.start()
    print(f"Buster OS kernel {get_version()} started.")
    return 0


def cmd_status(args) -> int:
    kernel = Kernel(config=Config())
    status = kernel.status()
    print(f"State:    {status['state']}")
    print(f"Version:  {status['version']}")
    print(f"EventBus: {'running' if status['event_router_running'] else 'stopped'}")
    print(f"Scheduler:{'running' if status['scheduler_running'] else 'stopped'}")
    print(f"Agents:   {', '.join(status['agents']) or 'none'}")
    print(f"Jobs:     {len(status['jobs'])}")
    return 0


def cmd_version(args) -> int:
    print(get_version())
    return 0


def cmd_help(args) -> int:
    print(
        "Buster OS - AI-native environment for Termux\n"
        "\n"
        "Usage: buster <command>\n"
        "\n"
        "Commands:\n"
        "  start     Start the Buster kernel\n"
        "  status    Show kernel status\n"
        "  version   Print the installed version\n"
        "  help      Show this help\n"
    )
    return 0


COMMANDS = {
    "start": cmd_start,
    "status": cmd_status,
    "version": cmd_version,
    "help": cmd_help,
}


def dispatch_command(command: str, args) -> int:
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"[ERROR] Unknown command '{command}'", file=sys.stderr)
        cmd_help(args)
        return 2
    return handler(args)
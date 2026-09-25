"""busterctl — Buster OS system control tool.

Runs the existing Buster CLI lifecycle against the canonical install layout
(/etc/buster, /var/lib/buster, /var/log/buster on a deployed Buster OS).
Same single Kernel, same commands.

The canonical install/state path is resolved once by ``buster.install`` and
every consumer (CLI, daemon, RuntimeLock/Client, RemoteKernel, GUI) uses it,
so busterctl never hard-codes a second path.
"""

import os
import sys

from buster.system import prepare_env

_LIFECYCLE_AND_MANAGEMENT = {
    "bootstrap", "start", "status", "shell", "stop", "daemon",
    "doctor", "version", "caps", "grant", "deny", "run", "config",
    "jobs", "audit", "intel", "goal", "health", "launch",
}


def main(argv=None) -> int:
    prepare_env()
    argv = list(sys.argv[1:] if argv is None else argv)
    from buster.cli.main import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
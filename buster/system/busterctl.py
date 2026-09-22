"""busterctl — Buster OS system control tool.

Runs the existing Buster CLI lifecycle against the Buster OS system layout
(/etc/buster, /var/lib/buster, /var/log/buster) instead of the v0.2.0
application layout. Same single Kernel, same commands.
"""

import os
import sys

from buster.system import prepare_env, system_install_path

_LIFECYCLE_AND_MANAGEMENT = {
    "bootstrap", "start", "status", "shell", "stop", "daemon",
    "doctor", "version", "caps", "grant", "deny", "run", "config",
    "jobs", "audit", "intel", "goal", "health",
}


def main(argv=None) -> int:
    prepare_env()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in _LIFECYCLE_AND_MANAGEMENT:
        if "--install-path" not in argv:
            argv = [argv[0], "--install-path", system_install_path()] + argv[1:]
    from buster.cli.main import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
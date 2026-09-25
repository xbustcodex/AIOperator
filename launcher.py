"""Buster OS launcher.

The root entry point only bootstraps and connects to the single daemon. It
never constructs a Kernel in the launcher process.
"""

import argparse
import os
import sys

from buster.install import resolve_install_path
from buster.launch import LaunchError, ensure_bootstrap, ensure_runtime
from buster.logging import setup_logging


def main(argv: list | None = None, shell: bool = False) -> int:
    parser = argparse.ArgumentParser(prog="launcher.py")
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--install-path", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    launch_shell = shell or args.shell
    install = resolve_install_path(explicit=args.install_path)
    setup_logging(os.path.join(install, "logs"), "INFO")

    try:
        ensure_bootstrap(install)
        ensure_runtime(install)
    except LaunchError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if launch_shell:
        from buster.runtime import RemoteKernel, RuntimeClient
        from buster.shell.session import InteractiveShell
        client = RuntimeClient(install)
        return InteractiveShell(kernel=RemoteKernel(client)).repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())

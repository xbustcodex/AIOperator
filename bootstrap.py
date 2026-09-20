"""Buster OS bootstrap entry point.

Boots the kernel, materializes the environment (layout, grants, seeds),
runs optional doctor checks, and can drop into the interactive shell.

Usage:
    python bootstrap.py            # bootstrap and exit
    python bootstrap.py --check    # bootstrap + doctor health checks
    python bootstrap.py --shell    # bootstrap + interactive shell
    python bootstrap.py --skip-grants   # do not apply default grants
"""

import argparse
import sys

from buster.config import Config
from buster.kernel.core import Kernel
from buster.version import get_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buster-bootstrap",
        description="Bootstrap the Buster OS environment.",
    )
    parser.add_argument("--shell", action="store_true",
                        help="launch the interactive shell after bootstrapping")
    parser.add_argument("--check", action="store_true",
                        help="run doctor health checks after bootstrapping")
    parser.add_argument("--skip-grants", action="store_true",
                        help="skip applying security default grants")
    parser.add_argument("--install-path", default=None,
                        help="override the install path (used by build/tests)")
    return parser


def main(argv: list | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    config = Config()
    if args.install_path:
        config.set("install_path", args.install_path)

    from buster.bootstrap import BootstrapManager
    from buster.logging import setup_logging

    install_path = config.get("install_path", sys_generic_home() + "/.buster/")
    setup_logging(install_path + "/logs", config.get("logging_level", "INFO"))

    kernel = Kernel(config=config)
    kernel.start()
    try:
        bootstrap = BootstrapManager(kernel)
        summary = bootstrap.run(apply_grants=not args.skip_grants)
        kernel.world_model.component_status("bootstrap", "done")

        print(f"Buster OS {summary['version']} bootstrapped.")
        print(f"  install:   {summary['install_path']}")
        print(f"  layout:    {len(summary['layout'])} dir(s) ready")
        print(f"  grants:    {summary['grants_applied'] or '(none)'}")
        print(f"  first_run: {summary['first_run']}")

        if args.check:
            from buster.diagnostics.doctor import run_doctor
            report = run_doctor()
            print()
            for check in report.checks:
                state = "PASS" if check["ok"] else "FAIL"
                print(f"  [{'x' if check['ok'] else ' '}] {check['name']:<22} {state} {check['detail']}")
            if report.failed:
                print(f"\n{report.failed} check(s) failed.")
                return 1

        if args.shell:
            from buster.shell.session import InteractiveShell
            return InteractiveShell(kernel=kernel).repl()
        return 0
    finally:
        kernel.stop()


def sys_generic_home() -> str:
    import os
    return os.path.expanduser("~")


if __name__ == "__main__":
    sys.exit(main())
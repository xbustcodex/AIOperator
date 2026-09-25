"""Buster OS bootstrap entry point.

Offline installation/initialization only: materializes the directory
layout, writes default configuration and records the first-run marker.
Aligns with the lifecycle command ``buster bootstrap``.

    python bootstrap.py                    # offline bootstrap
    python bootstrap.py --check            # bootstrap + doctor checks
    python bootstrap.py --shell            # bootstrap then start + shell
    python bootstrap.py --install-path P   # override install directory
"""

import argparse
import os
import sys

from buster.config import Config
from buster.install import resolve_install_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buster-bootstrap",
        description="Offline bootstrap (installation) for Buster OS.",
    )
    parser.add_argument("--shell", action="store_true",
                        help="bootstrap, then start the runtime and enter the shell")
    parser.add_argument("--check", action="store_true",
                        help="run doctor health checks after bootstrapping")
    parser.add_argument("--install-path", default=None,
                        help="override the install path")
    return parser


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    install = resolve_install_path(explicit=args.install_path)
    config = Config(config_path=os.path.join(install, "config", "config.json"),
                    install_path=install)

    from buster.bootstrap import bootstrap_offline
    summary = bootstrap_offline(config, install_path=install)

    print(f"Buster OS {summary['version']} bootstrap complete.")
    print(f"  install:   {summary['install_path']}")
    print(f"  layout:    {summary['layout_created'] or '(already present)'}")
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
        from buster.cli.commands import cmd_start, cmd_shell
        code = cmd_start(["--install-path", install])
        if code != 0:
            return code
        return cmd_shell(["--install-path", install])
    return 0


if __name__ == "__main__":
    sys.exit(main())
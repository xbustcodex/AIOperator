"""Buster OS installer - idempotent environment setup for TerminalP.

TerminalP is the first-class phone host; Termux-class environments are also
recognized. Installation only proceeds inside a valid Android terminal host.
"""

import logging
import os
import sys

from buster.android_integration.device import host_identity, is_termux_compatible
from buster.config import Config
from buster.logging import setup_logging

INSTALL_BASE = os.path.expanduser("~/.buster")

SUBDIRS = [
    "config",
    "cache",
    "logs",
    "state",
    "memory",
    "models",
    "agents",
    "packages",
    "workspaces",
    "backups",
]


def verify_host_environment() -> bool:
    return is_termux_compatible()


def create_directories(base_path: str) -> None:
    for subdir in SUBDIRS:
        os.makedirs(os.path.join(base_path, subdir), exist_ok=True)


def main() -> int:
    if not verify_host_environment():
        print("[FAIL] Not running inside a supported phone terminal.")
        print("       Buster OS targets TerminalP (Termux-class Android terminal) on Android.")
        return 1

    create_directories(INSTALL_BASE)
    setup_logging(os.path.join(INSTALL_BASE, "logs"), "INFO")
    logging.info("Starting Buster OS installation...")

    config = Config(config_path=os.path.join(INSTALL_BASE, "config", "config.json"))
    logging.info("Configuration initialized at %s", config.config_path)

    print(f"\nBuster OS installation completed successfully on {host_identity()}!")
    print("Run 'buster bootstrap' then 'buster start' to launch the environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
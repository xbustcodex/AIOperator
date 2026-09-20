"""Buster OS installer - idempotent environment setup for Termux."""

import logging
import os
import sys

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


def verify_termux_environment() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "")


def create_directories(base_path: str) -> None:
    for subdir in SUBDIRS:
        os.makedirs(os.path.join(base_path, subdir), exist_ok=True)


def main() -> int:
    if not verify_termux_environment():
        print("[FAIL] Not running inside a Termux environment.")
        print("       Buster OS targets Termux on Android.")
        return 1

    create_directories(INSTALL_BASE)
    setup_logging(os.path.join(INSTALL_BASE, "logs"), "INFO")
    logging.info("Starting Buster OS installation...")

    config = Config(config_path=os.path.join(INSTALL_BASE, "config", "config.json"))
    logging.info("Configuration initialized at %s", config.config_path)

    print("\nBuster OS installation completed successfully!")
    print("Run 'buster start' to launch the environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
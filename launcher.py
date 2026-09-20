"""Buster OS launcher - initialises the kernel and starts the environment.

Usage:
    python launcher.py            # boot kernel, then shut down cleanly
    python launcher.py --shell    # boot kernel and enter the interactive shell
"""

import logging
import sys

from buster.config import Config
from buster.kernel.core import Kernel
from buster.logging import setup_logging


def main(argv: list | None = None, shell: bool = False) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)
    launch_shell = shell or "--shell" in args

    config = Config()
    setup_logging(
        config.get("install_path", __import__("os").path.expanduser("~/.buster/")) + "/logs",
        config.get("logging_level", "INFO"),
    )

    kernel = Kernel(config=config)
    kernel.start()
    logging.info("Buster OS kernel started.")

    try:
        if launch_shell:
            from buster.shell.session import InteractiveShell
            return InteractiveShell(kernel=kernel).repl()
    finally:
        kernel.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
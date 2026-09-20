"""Buster OS launcher - initialises the kernel and starts the shell."""

import logging
import sys

from buster.config import Config
from buster.kernel.core import Kernel
from buster.logging import setup_logging


def main() -> int:
    config = Config()
    setup_logging(
        config.get("install_path", __import__("os").path.expanduser("~/.buster/")) + "/logs",
        config.get("logging_level", "INFO"),
    )

    kernel = Kernel(config=config)
    kernel.start()
    logging.info("Buster OS kernel started; shell pending.")

    # TODO: initialize interactive shell / agent loop on top of the kernel.
    kernel.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
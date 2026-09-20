"""Module entry point: ``python -m buster.cli``."""

import sys

from buster.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
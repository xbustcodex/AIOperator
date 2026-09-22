"""Central version definition for Buster OS."""

__version__ = "0.3.0"

VERSION = __version__
VERSION_MAJOR = 0
VERSION_MINOR = 3
VERSION_PATCH = 0


def get_version() -> str:
    return __version__
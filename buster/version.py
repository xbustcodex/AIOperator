"""Central version definition for Buster OS."""

__version__ = "0.3.1"

VERSION = __version__
VERSION_MAJOR = 0
VERSION_MINOR = 3
VERSION_PATCH = 1


def get_version() -> str:
    return __version__
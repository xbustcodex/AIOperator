"""Buster OS GUI — local consumer frontend.

The GUI is a client of the Buster daemon: it uses the existing
RemoteKernel/RuntimeClient RPC boundary and never instantiates a Kernel,
EventRouter, Scheduler, memory authority or agent system. The daemon and
persistent state continue independently of the UI.
"""

from buster.version import get_version

GUI_NAME = "Buster OS GUI"
GUI_VERSION = get_version()

__all__ = [
    "DEFAULT_PORT",
    "GUI_NAME",
    "GUI_VERSION",
    "GuiServer",
    "run_gui",
    "server",
]


def __getattr__(name):
    """Lazily expose the server surface without importing it eagerly.

    Keeping `buster.gui.server` out of package import time avoids the
    double-import that breaks `python -m buster.gui.server`. `DEFAULT_PORT`
    comes from the server module so there is a single source of truth.
    """
    if name in ("GuiServer", "run_gui", "DEFAULT_PORT", "server"):
        from buster.gui import server
        return getattr(server, name)
    raise AttributeError(name)
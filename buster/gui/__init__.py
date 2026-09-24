"""Buster OS GUI — local consumer frontend.

The GUI is a client of the Buster daemon: it uses the existing
RemoteKernel/RuntimeClient RPC boundary and never instantiates a Kernel,
EventRouter, Scheduler, memory authority or agent system. The daemon and
persistent state continue independently of the UI.
"""

from buster.gui.server import DEFAULT_PORT, GuiServer, run_gui
from buster.version import get_version

GUI_NAME = "Buster OS GUI"
GUI_VERSION = get_version()

__all__ = ["DEFAULT_PORT", "GUI_NAME", "GUI_VERSION", "GuiServer", "run_gui"]
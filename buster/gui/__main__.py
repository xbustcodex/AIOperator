"""Buster OS GUI server command-line entry point.

    python -m buster.gui [--install-path DIR] [--port 8468]
    python -m buster.gui.server [--install-path DIR]   (equivalent)

The GUI is a pure client of the running Buster daemon. When
``--install-path`` is omitted the canonical resolver (buster.install) decides
the install/state location — the same one bootstrap, start, busterctl, doctor
and the shell use.
"""

import argparse
import logging
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="buster-gui",
                                     description="Buster OS consumer UI server")
    parser.add_argument("--install-path", default=None,
                        help="canonical install dir (resolved when omitted)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8468)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    from buster.install import resolve_install_path
    install = resolve_install_path(explicit=args.install_path)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    from buster.gui.server import GuiServer
    GuiServer(install, host=args.host, port=args.port).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Buster OS GUI server command-line entry point.

    python -m buster.gui --install-path /var/lib/buster [--port 8468]
    python -m buster.gui.server --install-path /var/lib/buster   (equivalent)

The GUI is a pure client of the running Buster daemon.
"""

import argparse
import logging
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="buster-gui",
                                     description="Buster OS consumer UI server")
    parser.add_argument("--install-path", default="/var/lib/buster")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8468)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    from buster.gui.server import GuiServer
    GuiServer(args.install_path, host=args.host, port=args.port).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
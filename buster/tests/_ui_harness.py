"""UI review harness: brings up the real Buster runtime + GUI server in one
process and prints the GUI base URL, then stays alive until terminated.

    python _ui_harness.py > harness.out

The Playwright driver reads the base URL from harness.out.
"""

import os
import sys
import tempfile
import threading
import time

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from buster.config import Config
from buster.kernel.core import Kernel
from buster.runtime import RuntimeServer


def main() -> int:
    install = tempfile.mkdtemp()
    config = Config(config_path=os.path.join(install, "config.json"))
    config.set("install_path", install + os.sep)

    kernel = Kernel(config=config)
    runtime = RuntimeServer(kernel, install)
    if not runtime.start():
        print("FAIL runtime")
        return 1
    threading.Thread(target=runtime.serve, daemon=True).start()

    # grant read-safe consumer capabilities so real state flows
    for action in ("fs.list", "fs.read", "time.now", "android.info"):
        kernel.permissions.grant(action)

    from buster.gui.server import GuiServer
    gui = GuiServer(install, host="127.0.0.1", port=0)
    threading.Thread(target=gui.serve_forever, daemon=True).start()
    time.sleep(0.5)

    print(f"BASE_URL=http://127.0.0.1:{gui.port}", flush=True)
    url_file = os.environ.get("BUSTER_HARNESS_URL_FILE")
    if url_file:
        with open(url_file, "w", encoding="utf-8") as handle:
            handle.write(f"http://127.0.0.1:{gui.port}\n")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        gui.stop()
        runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Buster consumer launch: one command that brings up the whole product.

The consumer GUI is Buster's primary interface. Kernel, Runtime, RPC,
EventRouter, Scheduler, intelligence and provider infrastructure are
background plumbing and must not require manual startup by an ordinary
user. ``launch()`` is the single normal entry point:

    resolve canonical install
    -> bootstrap (offline, idempotent, never a second Kernel)
    -> ensure ONE daemon/runtime is online (reuse if healthy)
    -> wait for authoritative RPC readiness
    -> ensure the consumer GUI server is up (reuse if already running)
    -> present the interface (best-effort, deployment-bound)

Every step is idempotent and concurrency-safe. The GUI remains a pure
RPC client: launching never embeds a second Kernel or runtime in the UI
process.

Lifecycle behaviours covered by :func:`launch`:
- first launch        -> bootstrap, start runtime, start GUI, open UI
- subsequent launch   -> reuse running runtime + GUI
- runtime already up  -> reuse (single-runtime invariant)
- GUI already up      -> reuse
- stale runtime lock  -> daemon start (RuntimeLock) sweeps dead locks
- runtime crash       -> next launch restarts the daemon
- GUI crash/restart   -> next launch restarts the GUI
- failed bootstrap    -> LaunchError (friendly message, no GUI loop)
- failed RPC readiness-> LaunchError with recovery guidance
"""

import json
import logging
import os
import subprocess
import sys
import time

from buster.install import resolve_install_path
from buster.runtime import (
    RuntimeLock,
    recover_wedged_runtime,
    runtime_ready,
    spawn_daemon,
    wait_online,
)

log = logging.getLogger("buster.launch")

DEFAULT_GUI_PORT = 8468
GUI_PID_NAME = "gui.pid"
RPC_READY_TIMEOUT = 60.0


class LaunchError(Exception):
    """User-facing launch failure with recovery guidance."""


def _gui_pid_path(install: str) -> str:
    from buster.runtime import state_dir
    return os.path.join(state_dir(install), GUI_PID_NAME)


def _pid_alive(pid: int) -> bool:
    from buster.runtime import _pid_alive
    return _pid_alive(pid)


def ensure_bootstrap(install: str) -> dict:
    """Offline bootstrap whenever needed; idempotent, never a Kernel."""
    from buster.bootstrap import bootstrap_offline
    from buster.config import Config
    config = Config(config_path=os.path.join(install, "config", "config.json"),
                    install_path=install)
    return bootstrap_offline(config, install_path=install)


def ensure_runtime(install: str, wait: float = RPC_READY_TIMEOUT) -> dict:
    """Ensure exactly one live runtime daemon; reuse a healthy one."""
    lock = RuntimeLock(install)
    if lock.is_online():
        if runtime_ready(install, timeout=min(2.0, wait)):
            info = lock.read() or {}
            log.info("Runtime already online (pid %s); reusing.", info.get("pid"))
            return {"action": "reused", "pid": info.get("pid")}
        log.warning("Runtime lock is present but RPC is not ready; recovering it.")
        if not recover_wedged_runtime(install, timeout=min(5.0, wait)):
            raise LaunchError(
                "Buster found a runtime that is not responding and could not "
                "recover it safely. Stop that process, then launch again.")

    spawn_daemon(install)
    if not wait_online(install, timeout=wait):
        raise LaunchError(
            "Buster could not bring its runtime online. Check that the install "
            f"directory is writable ({install}) and run 'buster status' or "
            "'buster doctor' for details.")
    info = lock.read() or {}
    return {"action": "started", "pid": info.get("pid")}


def gui_ping(port: int = DEFAULT_GUI_PORT) -> dict | None:
    """Return the live GUI's ping document, or None when nothing answers."""
    import json as _json
    import urllib.request
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ping", timeout=2.0) as resp:
            if resp.status != 200:
                return None
            return _json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def gui_is_live(port: int = DEFAULT_GUI_PORT) -> bool:
    """True when a Buster GUI already answers on the canonical port."""
    return gui_ping(port) is not None


def _same_install(ping: dict, install: str) -> bool:
    """A GUI may only be reused when it serves THIS canonical install."""
    served = ping.get("install_path")
    if not served:
        # Older GUI builds did not report install_path; refuse to adopt them
        # rather than risk talking to a foreign runtime view.
        return False
    try:
        return os.path.normcase(os.path.abspath(served)) == \
            os.path.normcase(os.path.abspath(install))
    except (OSError, ValueError):
        return False


def ensure_gui(install: str, port: int = DEFAULT_GUI_PORT,
               wait: float = 30.0) -> dict:
    """Ensure the consumer GUI server runs against this exact install.

    Idempotent: an existing GUI for the same canonical install is reused.
    A GUI bound to the port but serving a *different* install is never
    adopted — that would silently show a foreign runtime.
    """
    pid_path = _gui_pid_path(install)
    ping = gui_ping(port)
    if ping is not None:
        if _same_install(ping, install):
            return {"action": "reused", "url": f"http://127.0.0.1:{port}",
                    "pid": _read_pid(pid_path)}
        raise LaunchError(
            f"Another Buster interface is already using port {port} for a "
            f"different installation ({ping.get('install_path') or 'unknown'}). "
            "Stop it first, or start this Buster on another port.")

    env = dict(os.environ)
    env.setdefault("BUSTER_INSTALL", install)
    child = subprocess.Popen(
        [sys.executable, "-m", "buster.gui.server", "--install-path", install,
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True,
    )
    os.makedirs(os.path.dirname(pid_path), exist_ok=True)
    _write_pid(pid_path, child.pid)

    deadline = time.time() + wait
    while time.time() < deadline:
        ping = gui_ping(port)
        if ping is not None and _same_install(ping, install):
            return {"action": "started", "url": f"http://127.0.0.1:{port}",
                    "pid": child.pid}
        if child.poll() is not None:
            break
        time.sleep(0.2)

    raise LaunchError(
        "Buster's interface could not start. The runtime is running; run "
        f"'python -m buster.gui.server --install-path {install}' to see logs.")


def _present_via_bridge(url: str) -> tuple:
    """Ask the authenticated TerminalP bridge to present the interface.

    PRoot is a filesystem/uid emulator, not an Android Binder/Intent
    transport: the guest has no route to the host's activity manager, and no
    host API binary is necessarily visible inside the guest. So presentation
    is delegated to the one sanctioned integration boundary -- the typed
    ``present`` operation of the authenticated TerminalP bridge -- which
    constructs the bounded Android action itself.

    ``present`` takes no argument. The URL is checked here purely to refuse
    presenting something that is not this runtime's own loopback interface;
    it is never forwarded to the host.
    """
    if not url.startswith("http://127.0.0.1:"):
        return False, "refusing to present a non-loopback interface"
    import sys as _sys
    try:
        completed = subprocess.run(
            [_sys.executable, "-m", "buster.cli", "exec", "present"],
            timeout=20.0, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"present bridge unavailable ({type(exc).__name__})"
    if completed.returncode != 0:
        return False, "present bridge refused the request"
    try:
        document = json.loads(completed.stdout.decode("utf-8", "replace"))
    except ValueError:
        return False, "present bridge returned no usable document"
    if not document.get("ready"):
        return False, f"present bridge not ready: {document.get('error')}"
    return True, "presented via the authenticated TerminalP bridge"


def open_ui(url: str) -> tuple:
    """Best-effort, deployment-bound presentation of the local UI.

    Ordering, most specific integration first:

    1. a host Termux-class ``*-api open-url`` binary, when one is actually
       available to the guest;
    2. the authenticated, typed ``present`` operation of the TerminalP
       bridge -- the sole Buster->Android integration boundary;
    3. a Linux desktop opener;
    4. printing the URL, which is always the final recovery path.

    Presentation is never load-bearing: every failure falls through, and a
    successful runtime/GUI launch is never converted into a failure.
    """
    if os.environ.get("BUSTER_NO_OPEN"):
        return False, "opening disabled (BUSTER_NO_OPEN)"

    import shutil
    host_bin = shutil.which("terminalp-api") or shutil.which("termux-api")
    if host_bin:
        try:
            subprocess.run([host_bin, "open-url", url], timeout=10.0,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"{host_bin} open-url {url}"
        except (OSError, subprocess.TimeoutExpired):
            pass

    presented, reason = _present_via_bridge(url)
    if presented:
        return True, reason

    for opener in ("xdg-open", "htmlview", "gio"):
        path = shutil.which(opener)
        if path:
            try:
                subprocess.Popen([path, url], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True, f"{opener} {url}"
            except OSError:
                continue
    print(f"\nBuster is ready: open {url}\n")
    return False, f"no opener available; printed URL ({reason})"


def launch(install: str = None, port: int = DEFAULT_GUI_PORT,
           open_browser: bool = True, wait: float = RPC_READY_TIMEOUT) -> dict:
    """Run the complete consumer launch flow (idempotent, one runtime)."""
    install = resolve_install_path(explicit=install)
    if not os.path.isdir(install):
        os.makedirs(install, exist_ok=True)

    bootstrap = ensure_bootstrap(install)
    runtime = ensure_runtime(install, wait=wait)
    gui = ensure_gui(install, port=port)
    opened = False
    reason = ""
    if open_browser:
        try:
            opened, reason = open_ui(gui["url"])
        except Exception as exc:  # noqa: BLE001
            log.warning("UI presentation failed: %s", exc)

    return {
        "install": install,
        "bootstrap": bootstrap,
        "runtime": runtime,
        "gui": gui,
        "url": gui["url"],
        "opened": opened,
        "open_reason": reason,
    }


def _read_pid(path: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return int(handle.read().strip() or "0")
    except (OSError, ValueError):
        return None


def _write_pid(path: str, pid: int) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(pid) + "\n")
    except OSError:
        log.warning("could not write GUI pid file %s", path)
"""Logging subsystem for Buster OS."""

import logging
import os

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(log_dir: str, level: str = "INFO", console: bool = True) -> None:
    """Configure the root logging pipeline used by all Buster modules.

    Writes to ``log_dir/buster.log`` and, optionally, the console.
    Idempotent: safe to call multiple times.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "buster.log")

    level_value = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level_value)

    for handler in list(root.handlers):
        try:
            handler.acquire()
            handler.flush()
            handler.close()
        except (OSError, ValueError):
            pass
        finally:
            try:
                handler.release()
            except Exception:  # noqa: BLE001
                pass
        root.removeHandler(handler)

    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if console:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level_value,
        format=DEFAULT_FORMAT,
        handlers=handlers,
        force=True,
    )


class LoggerMixin:
    """Mixin providing a namespaced logger for Buster classes."""

    @property
    def logger(self) -> logging.Logger:
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return logging.getLogger(name)
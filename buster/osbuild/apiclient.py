"""Fetch helpers for the Buster OS rootfs build (stdlib urllib)."""

import gzip
import io
import logging
import urllib.error
import urllib.request
from typing import Optional

log = logging.getLogger("buster.osbuild.apiclient")


def fetch_bytes(url: str, timeout: float = 30.0, retries: int = 3) -> bytes:
    """Download a URL with bounded retries."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "buster-os-rootfs-builder/1.0",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
            log.warning("fetch attempt %d/%d failed for %s: %s",
                        attempt, retries, url, exc)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def fetch_packages_index(url: str, timeout: float = 30.0) -> str:
    """Fetch a Packages index (plain or .gz) and return decoded text."""
    raw = fetch_bytes(url, timeout=timeout)
    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def gunzip_bytes(raw: bytes) -> bytes:
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def stream_bytes(raw: bytes) -> io.BytesIO:
    return io.BytesIO(raw)
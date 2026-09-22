"""Read .deb archives and extract their payload without dpkg (stdlib only).

Debian .deb files are `ar` archives containing:

  debian-binary   (format version text)
  control.tar.*   (control metadata + maintainer scripts)
  data.tar.*      (the payload files that populate the filesystem)

We extract payload and metadata directly so a rootfs can be populated on any
host. No maintainer scripts are executed on the build host; the rootfs is
configured at first boot by dpkg.
"""

import io
import logging
import tarfile
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("buster.osbuild.deb")

DEB_BINARY_VERSION = "2.0"

_AR_NAME_LEN = 16
_AR_MTIME = 12
_AR_UID = 6
_AR_GID = 6
_AR_MODE = 8
_AR_SIZE = 10
_AR_MAGIC = 2
_HEADER_LEN = 60


def parse_ar(data: bytes) -> list[tuple[str, bytes]]:
    """Parse an `ar` (Unix Archive) blob into (name, data) members.

    Header layout (GNU/BSD): name(16) mtime(12) uid(6) gid(6) mode(8)
    size(10) magic(2).
    """
    if data[:8] != b"!<arch>\n":
        raise ValueError("not a valid ar archive")
    offset = 8
    members = []
    while offset + _HEADER_LEN <= len(data):
        header = data[offset:offset + _HEADER_LEN]
        name = header[0:16].decode("utf-8", "replace").rstrip(" /")
        size_text = header[48:58].decode("ascii", "replace").strip()
        try:
            size = int(size_text)
        except ValueError:
            break
        data_start = offset + _HEADER_LEN
        body_start = data_start + size
        if data_start > len(data) or body_start > len(data):
            break
        members.append((name, data[data_start:body_start]))
        offset = body_start
        if offset % 2:  # ar pads odd sizes / terminator
            offset += 1
    # drop the special `///` symbol table member if present
    members = [m for m in members if not m[0].startswith("//")]
    return members


@dataclass
class DebContent:
    control: dict = field(default_factory=dict)
    payload_files: list[str] = field(default_factory=list)
    conffiles: list[str] = field(default_factory=list)
    scripts: dict = field(default_factory=dict)  # name -> script text

    def names(self) -> list[str]:
        return list(self.control.keys())


def data_tar(data: bytes) -> "tarfile.TarFile":
    """Return an opened tarfile of a .deb payload (data.tar.*)."""
    for name, blob in parse_ar(data):
        if name.startswith("data.tar"):
            return tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
    raise ValueError("no data.tar member in .deb")


def extract(data: bytes) -> DebContent:
    """Parse a .deb blob and return control info + payload file list."""
    members = parse_ar(data)
    control_blob: Optional[bytes] = None
    data_blob: Optional[bytes] = None
    for name, blob in members:
        if name.startswith("control.tar"):
            control_blob = blob
        elif name.startswith("data.tar"):
            data_blob = blob

    content = DebContent()

    if control_blob is not None:
        with tarfile.open(fileobj=io.BytesIO(control_blob), mode="r:*") as tar:
            for member in tar.getmembers():
                clean = member.name.lstrip("./")
                if member.isfile():
                    data = tar.extractfile(member).read() if tar.extractfile(member) else b""
                    if clean == "control":
                        content.control = parse_control(data.decode("utf-8", "replace"))
                    elif clean == "conffiles":
                        content.conffiles = [ln.strip() for ln in data.decode().splitlines() if ln.strip()]
                    elif clean.startswith("md5sums"):
                        pass
                    elif clean in ("preinst", "postinst", "prerm", "postrm", "config", "templates"):
                        content.scripts[clean] = data.decode("utf-8", "replace")

    if data_blob is not None:
        with tarfile.open(fileobj=io.BytesIO(data_blob), mode="r:*") as tar:
            for member in tar.getmembers():
                if (member.isreg() or member.isdir() or member.issym()) and member.name != "./":
                    content.payload_files.append(member.name.lstrip("./"))

    return content


def parse_control(text: str) -> dict:
    fields: dict[str, str] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] in (" ", "\t") and current:
            fields[current] += " " + line.strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            current = key.strip()
            fields[current] = value.strip()
    return fields
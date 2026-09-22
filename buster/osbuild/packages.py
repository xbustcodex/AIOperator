"""Debian Packages index parsing (stdlib only)."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PackageRecord:
    package: str
    version: str
    architecture: str = "all"
    section: str = ""
    depends: str = ""
    pre_depends: str = ""
    provides: str = ""
    filename: str = ""
    size: int = 0
    md5sum: str = ""
    sha256: str = ""
    priority: str = "optional"
    essential: bool = False

    def provides_names(self) -> list[str]:
        parts = []
        for chunk in (self.provides or "").split(","):
            name = chunk.strip().split(" ")[0].split("(")[0].strip()
            if name:
                parts.append(name)
        return parts


def parse_packages(text: str) -> list[PackageRecord]:
    """Parse a Debian Packages index text into records."""
    records: list[PackageRecord] = []
    stanza: dict[str, str] = {}
    current_field: Optional[str] = None

    def flush():
        nonlocal stanza
        if stanza.get("Package"):
            records.append(_record_from_stanza(stanza))
        stanza = {}

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line == "":
            flush()
            current_field = None
            continue
        if line[0] in (" ", "\t"):
            if current_field and current_field in stanza:
                stanza[current_field] += " " + line.strip()
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            key = field.strip()
            current_field = key
            stanza[key] = value.strip()
            if key == "Description":
                # multiline description follows; ignored for our purposes
                pass
        else:
            current_field = None
    flush()
    return records


def _record_from_stanza(stanza: dict[str, str]) -> PackageRecord:
    deps = stanza.get("Depends", "")
    pre = stanza.get("Pre-Depends", "")
    provides = stanza.get("Provides", "")
    return PackageRecord(
        package=stanza["Package"],
        version=stanza.get("Version", "0"),
        architecture=stanza.get("Architecture", "all"),
        section=stanza.get("Section", ""),
        depends=", ".join(_norm(deps) + _norm(pre)),
        pre_depends=pre,
        provides=provides or "",
        filename=stanza.get("Filename", ""),
        size=int(stanza.get("Size", "0") or 0),
        md5sum=stanza.get("MD5sum", ""),
        sha256=stanza.get("SHA256", ""),
        priority=stanza.get("Priority", "optional"),
        essential=stanza.get("Essential", "no").lower().startswith("yes"),
    )


def _norm(dep_str: str) -> list[str]:
    return [d.strip() for d in dep_str.split(",") if d.strip()]
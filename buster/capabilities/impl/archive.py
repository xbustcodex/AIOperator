"""Archive (zip / tar.gz) capability."""

import os
import tarfile
import zipfile
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class ArchiveCapability(Capability):
    """Create and extract zip / tar.gz archives."""

    name = "archive"
    actions_list = ["archive.zip", "archive.unzip", "archive.tgz", "archive.untgz"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        try:
            if ctx.action == "archive.zip":
                return CapabilityResult.ok(self._zip(extra))
            if ctx.action == "archive.unzip":
                return CapabilityResult.ok(self._unzip(extra))
            if ctx.action == "archive.tgz":
                return CapabilityResult.ok(self._tgz(extra))
            if ctx.action == "archive.untgz":
                return CapabilityResult.ok(self._untgz(extra))
        except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
            return CapabilityResult.fail(f"{type(exc).__name__}: {exc}")
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _resolve_paths(extra: dict) -> tuple[str, list[str]]:
        target = extra.get("target")
        sources = extra.get("sources")
        if not target or not sources:
            raise ValueError("archive requires 'target' and 'sources'")
        if isinstance(sources, str):
            sources = [sources]
        os.makedirs(os.path.dirname(os.path.abspath(target)) or ".", exist_ok=True)
        return target, list(sources)

    def _zip(self, extra: dict) -> dict:
        target, sources = self._resolve_paths(extra)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in sources:
                self._add_to_zip(archive, source)
        return {"target": target, "entries": len(sources)}

    @staticmethod
    def _add_to_zip(archive: zipfile.ZipFile, source: str) -> None:
        if os.path.isdir(source):
            for root, _dirs, files in os.walk(source):
                for name in files:
                    full = os.path.join(root, name)
                    archive.write(full, os.path.relpath(full, os.path.dirname(source.rstrip(os.sep))))
        else:
            archive.write(source, os.path.basename(source))

    def _unzip(self, extra: dict) -> dict:
        source = extra.get("source")
        dest = extra.get("dest", ".")
        if not source:
            raise ValueError("Missing 'source'")
        with zipfile.ZipFile(source, "r") as archive:
            extracted = archive.namelist()
            archive.extractall(dest)
        return {"source": source, "dest": dest, "entries": len(extracted)}

    def _tgz(self, extra: dict) -> dict:
        target, sources = self._resolve_paths(extra)
        with tarfile.open(target, "w:gz") as archive:
            for source in sources:
                base = os.path.basename(source.rstrip(os.sep)) or source
                archive.add(source, arcname=base, recursive=True)
        return {"target": target, "entries": len(sources)}

    def _untgz(self, extra: dict) -> dict:
        source = extra.get("source")
        dest = extra.get("dest", ".")
        if not source:
            raise ValueError("Missing 'source'")
        with tarfile.open(source, "r:gz") as archive:
            members = archive.getmembers()
            archive.extractall(dest)
        return {"source": source, "dest": dest, "entries": len(members)}
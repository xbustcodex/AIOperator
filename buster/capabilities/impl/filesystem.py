"""Filesystem capability with delete protection."""

import os
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult
from buster.security.protection import ProtectedPathError


class FileSystemCapability(Capability):
    """Structured filesystem access: list/read/write/mkdir/delete/stat."""

    name = "filesystem"
    actions_list = [
        "fs.list", "fs.read", "fs.write", "fs.mkdir",
        "fs.delete", "fs.stat", "fs.exists", "fs.touch",
    ]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def _protection(self):
        if self.kernel is not None:
            return getattr(self.kernel, "security", None).protection
        return None

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        handler = getattr(self, f"_on_{ctx.action.replace('.', '_')}", None)
        if handler is None:
            return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")
        try:
            return handler(ctx.extra or {})
        except ProtectedPathError as exc:
            return CapabilityResult.fail(str(exc))
        except (OSError, ValueError) as exc:
            return CapabilityResult.fail(f"{type(exc).__name__}: {exc}")

    def _on_fs_list(self, extra: dict) -> CapabilityResult:
        path = extra.get("path", ".")
        entries = sorted(os.listdir(path))
        kinds = {e: "dir" if os.path.isdir(os.path.join(path, e)) else "file" for e in entries}
        return CapabilityResult.ok({"path": path, "entries": kinds})

    def _on_fs_read(self, extra: dict) -> CapabilityResult:
        path = extra.get("path")
        with open(path, "r", encoding=extra.get("encoding", "utf-8")) as f:
            return CapabilityResult.ok(f.read())

    def _on_fs_write(self, extra: dict) -> CapabilityResult:
        path = extra.get("path")
        content = extra.get("content", "")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding=extra.get("encoding", "utf-8")) as f:
            f.write(content)
        return CapabilityResult.ok({"path": path, "bytes": len(content)})

    def _on_fs_mkdir(self, extra: dict) -> CapabilityResult:
        os.makedirs(extra.get("path"), exist_ok=True)
        return CapabilityResult.ok({"path": extra.get("path")})

    def _on_fs_delete(self, extra: dict) -> CapabilityResult:
        path = extra.get("path")
        protection = self._protection()
        if protection is not None:
            protection.ensure_allowed(path)
        recursive = extra.get("recursive", False)
        if os.path.isdir(path) and not recursive:
            return CapabilityResult.fail("Directory delete requires recursive=true")
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
        return CapabilityResult.ok({"deleted": path})

    def _on_fs_stat(self, extra: dict) -> CapabilityResult:
        st = os.stat(extra.get("path"))
        return CapabilityResult.ok({
            "size": st.st_size,
            "mtime": st.st_mtime,
            "mode": st.st_mode,
        })

    def _on_fs_exists(self, extra: dict) -> CapabilityResult:
        return CapabilityResult.ok(os.path.exists(extra.get("path", "")))

    def _on_fs_touch(self, extra: dict) -> CapabilityResult:
        path = extra.get("path")
        with open(path, "a", encoding="utf-8"):
            os.utime(path, None)
        return CapabilityResult.ok({"path": path})
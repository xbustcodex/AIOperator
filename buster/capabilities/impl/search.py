"""File and text search capability."""

import fnmatch
import os
import re
from typing import Optional

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult

MAX_FOUND = 1000


class SearchCapability(Capability):
    """Glob files or grep text across a tree."""

    name = "search"
    actions_list = ["search.files", "search.text"]

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        try:
            if ctx.action == "search.files":
                return CapabilityResult.ok(self._files(extra))
            if ctx.action == "search.text":
                return CapabilityResult.ok(self._text(extra))
        except (OSError, ValueError) as exc:
            return CapabilityResult.fail(f"{type(exc).__name__}: {exc}")
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _files(extra: dict) -> dict:
        root = extra.get("path", ".")
        pattern = extra.get("pattern", "*")
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if fnmatch.fnmatch(name, pattern):
                    found.append(os.path.relpath(os.path.join(dirpath, name), root))
                    if len(found) >= MAX_FOUND:
                        return {"path": root, "pattern": pattern, "found": found,
                                "truncated": True}
        return {"path": root, "pattern": pattern, "found": found}

    @staticmethod
    def _text(extra: dict) -> dict:
        root = extra.get("path", ".")
        needle = extra.get("needle")
        if not needle:
            raise ValueError("Missing 'needle'")
        limit = int(extra.get("limit", 100))
        case_sensitive = bool(extra.get("case_sensitive", False))
        flags = 0 if case_sensitive else re.IGNORECASE
        matches = []
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                        for lineno, line in enumerate(handle, 1):
                            if re.search(needle, line, flags):
                                matches.append({
                                    "file": os.path.relpath(path, root),
                                    "line": lineno,
                                    "text": line.strip()[:200],
                                })
                                count += 1
                                if count >= limit:
                                    return {"needle": needle, "path": root,
                                            "matches": matches, "limit_hit": True}
                except OSError:
                    continue
        return {"needle": needle, "path": root, "matches": matches}
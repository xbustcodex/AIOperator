"""Delete protection for sensitive paths."""

import os
import re
from dataclasses import dataclass
from typing import Optional


class ProtectedPathError(PermissionError):
    pass


@dataclass
class DeleteProtection:
    """Guard list of paths from destructive operations.

    Patterns are absolute paths, directory prefixes (anything under
    ``<prefix>/``) or regex strings wrapped in ``re:``.
    """

    patterns: list[str] | None = None

    def __post_init__(self):
        self._patterns = list(self.patterns or [])
        self._compiled = [self._compile(p) for p in self._patterns]

    @staticmethod
    def _compile(pattern: str) -> re.Pattern:
        if pattern.startswith("re:"):
            return re.compile(pattern[3:])
        if pattern.endswith("/") or pattern.endswith(os.sep):
            prefix = os.path.abspath(pattern[:-1]) + os.sep
            return re.compile(r"^" + re.escape(prefix))
        return re.compile(r"^" + re.escape(os.path.abspath(pattern)) + r"(?:$|" + re.escape(os.sep) + r")")

    def protect(self, pattern: str) -> None:
        self._patterns.append(pattern)
        self._compiled.append(self._compile(pattern))

    def is_protected(self, path: str) -> bool:
        absolute = os.path.abspath(path)
        return any(p.match(absolute) for p in self._compiled)

    def ensure_allowed(self, path: Optional[str]) -> None:
        if path is None:
            return
        if self.is_protected(path):
            raise ProtectedPathError(
                f"Path is protected from destruction: {os.path.abspath(path)}"
            )

    def describe(self) -> list[str]:
        return list(self._patterns)
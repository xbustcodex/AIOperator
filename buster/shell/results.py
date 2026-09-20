"""Structured results for shell commands."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StructuredResult:
    """Normalized outcome of any shell/command/capability operation."""

    ok: bool
    command: str
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @classmethod
    def success(cls, command: str, data: Any = None, **meta) -> "StructuredResult":
        return cls(ok=True, command=command, data=data, meta=meta)

    @classmethod
    def failure(cls, command: str, error: str, **meta) -> "StructuredResult":
        return cls(ok=False, command=command, error=error, meta=meta)

    def render(self, verbosity: int = 1) -> str:
        title = self.meta.get("title", "")
        lines = []
        if title:
            lines.append(title)
        if self.ok:
            if self.data is None:
                lines.append("OK")
            elif isinstance(self.data, str):
                lines.append(self.data)
            elif isinstance(self.data, (list, tuple)):
                for item in self.data:
                    lines.append(format_item(item))
            else:
                lines.append(format_item(self.data))
        else:
            lines.append(f"ERROR: {self.error}")
        return "\n".join(lines)


def format_item(item: Any) -> str:
    if isinstance(item, dict):
        pairs = [f"{k}={v}" for k, v in item.items() if not str(k).startswith("_")]
        return " ".join(pairs)
    return str(item)
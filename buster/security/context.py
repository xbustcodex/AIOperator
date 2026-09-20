"""Execution context propagated through capability invocations."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SecurityContext:
    """Identify and privilege context of an invocation."""

    actor: str = "user"
    scope: Optional[str] = None
    elevated: bool = False
    source: str = "cli"
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Full invocation context: security plus shared operational state."""

    action: str
    security: SecurityContext = field(default_factory=SecurityContext)
    workspace: Optional[str] = None
    agent: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_inputs(cls, action: str, scope: Optional[str] = None,
                    actor: str = "user", source: str = "cli",
                    context: Optional[dict] = None) -> "ExecutionContext":
        ctx = context or {}
        return cls(
            action=action,
            security=SecurityContext(
                actor=ctx.get("actor") or actor,
                scope=scope or ctx.get("scope"),
                elevated=bool(ctx.get("elevated", False)),
                source=ctx.get("source") or source,
                metadata=ctx,
            ),
            workspace=ctx.get("workspace"),
            agent=ctx.get("agent"),
            extra={k: v for k, v in ctx.items() if k not in ("scope", "elevated")},
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "actor": self.security.actor,
            "scope": self.security.scope,
            "elevated": self.security.elevated,
            "source": self.security.source,
            "workspace": self.workspace,
            "agent": self.agent,
        }
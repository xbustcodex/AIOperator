"""Specialized agent roles over ONE shared agent architecture.

Roles are configuration over the existing PlannerAgent: each role carries a
focused system prompt and a capability-prefix allowlist. There is no second
agent framework; every agent shares the Kernel, execution context, event
system, permissions, memory and audit infrastructure.
"""

from dataclasses import dataclass, field
from typing import Optional

from buster.agents.planner import PlannerAgent


@dataclass
class AgentRole:
    name: str
    description: str
    prompt: str
    allowed_prefixes: tuple = field(default_factory=tuple)  # () = all allowed

    def allows(self, action: str) -> bool:
        if not self.allowed_prefixes:
            return True
        return any(action.startswith(prefix) for prefix in self.allowed_prefixes)


ROLES: dict[str, AgentRole] = {
    "planner": AgentRole(
        name="planner",
        description="decomposes goals into structured capability-based plans",
        prompt=("You are Buster's planner. Produce a plan as a single JSON "
                "step per turn. Prefer read/introspect actions first."),
        allowed_prefixes=(),
    ),
    "researcher": AgentRole(
        name="researcher",
        description="gathers facts via read-only capabilities",
        prompt=("You are Buster's researcher. You answer questions by "
                "observation with read-safe capabilities (search, fs.read, "
                "net, android)."),
        allowed_prefixes=("search.", "fs.list", "fs.read", "fs.stat", "net.", "android.", "time.", "pkg."),
    ),
    "builder": AgentRole(
        name="builder",
        description="creates files and runs build tooling",
        prompt=("You are Buster's builder. You build things by writing files "
                "and invoking build tooling via capabilities only."),
        allowed_prefixes=("fs.write", "fs.mkdir", "fs.touch", "python.", "git.", "archive.", "shell.run"),
    ),
    "tester": AgentRole(
        name="tester",
        description="runs tests and commands to check correctness",
        prompt=("You are Buster's tester. Verify outcomes by running tests "
                "and inspecting results with capabilities."),
        allowed_prefixes=("shell.run", "python.eval", "search.", "fs.read", "process."),
    ),
    "reviewer": AgentRole(
        name="reviewer",
        description="audits outputs and files for quality",
        prompt=("You are Buster's reviewer. Inspect artifacts and report "
                "findings with read-safe capabilities."),
        allowed_prefixes=("fs.read", "fs.list", "search.", "process.", "python.eval", "pkg."),
    ),
    "fixer": AgentRole(
        name="fixer",
        description="repairs issues found by other roles",
        prompt=("You are Buster's fixer. Repair reported problems by editing "
                "files or rerunning checks via capabilities."),
        allowed_prefixes=("fs.write", "fs.mkdir", "python.", "git.", "shell.run", "crypto."),
    ),
    "observer": AgentRole(
        name="observer",
        description="watches node state and reports signals",
        prompt=("You are Buster's observer. Report current node, device and "
                "environment state from observation capabilities."),
        allowed_prefixes=("android.", "process.", "net.", "pkg.", "time.", "search."),
    ),
    "memory-worker": AgentRole(
        name="memory-worker",
        description="organises memories and knowledge (read/synthesize only)",
        prompt=("You are Buster's memory worker. Inspect memory stores and "
                "summarize with read-safe capabilities. Never mutate policy."),
        allowed_prefixes=("fs.list", "fs.read", "search.", "python.eval"),
    ),
    "maintenance-worker": AgentRole(
        name="maintenance-worker",
        description="performs safe housekeeping under policy",
        prompt=("You are Buster's maintenance worker. Perform routine, "
                "bounded maintenance whose actions are individually granted."),
        allowed_prefixes=("process.", "pkg.", "fs.list", "archive."),
    ),
}


class RoleAgent(PlannerAgent):
    """A PlannerAgent scoped to a role (config, not a new architecture)."""

    name = "role"

    def __init__(self, kernel=None, role: str = "planner", max_steps: int = 6):
        super().__init__(kernel=kernel, max_steps=max_steps)
        if role not in ROLES:
            raise ValueError(f"unknown agent role '{role}'")
        self.role = self._role = ROLES[role]
        self.name = f"role:{role}"

    def _known_action(self, action: str) -> bool:
        return super()._known_action(action) and self._role.allows(action)

    def _build_transcript(self, target, provider):
        base = super()._build_transcript(target, provider)
        if base:
            base[0] = type(base[0])("system", self._role.prompt + "\n" + base[0].content)
        return base


def available_roles() -> list[str]:
    return sorted(ROLES.keys())


def describe_roles() -> list[dict]:
    return [{"name": r.name, "description": r.description,
             "allowed_prefixes": list(r.allowed_prefixes)}
            for r in ROLES.values()]
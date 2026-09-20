"""Agent lifecycle management for Buster OS.

Owns the set of active agents, spawning and destroying them, and routing
their lifecycle transitions through the event bus.
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

LIFECYCLE_EVENTS = ("agent.spawned", "agent.stopped", "agent.failed")


class AgentNotFoundError(Exception):
    pass


@dataclass
class AgentInfo:
    agent_id: str
    name: str
    status: str = "spawning"  # spawning | active | stopped | failed
    meta: dict = field(default_factory=dict)


class AgentManager:
    """Registry and lifecycle controller for agents."""

    def __init__(self, event_router):
        self._event_router = event_router
        self._agents: dict[str, AgentInfo] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("buster.kernel.agent_manager")

    def spawn(self, name: str, meta: Optional[dict] = None) -> AgentInfo:
        with self._lock:
            agent = AgentInfo(
                agent_id=uuid.uuid4().hex,
                name=name,
                status="spawning",
                meta=meta or {},
            )
            self._agents[agent.agent_id] = agent
        self._event_router.emit("agent.spawned", {"agent": agent.agent_id, "name": name})
        self.logger.info("Spawned agent '%s' (%s)", name, agent.agent_id[:8])
        return agent

    def activate(self, agent_id: str) -> None:
        agent = self.get(agent_id)
        agent.status = "active"
        self._event_router.emit("agent.started", {"agent": agent_id})

    def stop(self, agent_id: str) -> None:
        agent = self.get(agent_id)
        agent.status = "stopped"
        self._event_router.emit("agent.stopped", {"agent": agent_id})
        self.logger.info("Stopped agent %s", agent_id[:8])

    def fail(self, agent_id: str, reason: str) -> None:
        agent = self.get(agent_id)
        agent.status = "failed"
        agent.meta["failure_reason"] = reason
        self._event_router.emit("agent.failed", {"agent": agent_id, "reason": reason})

    def destroy(self, agent_id: str) -> None:
        with self._lock:
            self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentInfo:
        with self._lock:
            agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Unknown agent id '{agent_id}'")
        return agent

    def list_agents(self, status: Optional[str] = None) -> list[AgentInfo]:
        with self._lock:
            agents = list(self._agents.values())
        if status is not None:
            agents = [a for a in agents if a.status == status]
        return agents

    def shutdown_all(self) -> None:
        for agent in list(self.list_agents()):
            if agent.status in ("spawning", "active"):
                try:
                    self.stop(agent.agent_id)
                except Exception:  # noqa: BLE001
                    self.logger.exception("Failed stopping agent %s", agent.agent_id[:8])
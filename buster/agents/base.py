"""Base Agent abstraction and run bookkeeping."""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class AgentRun:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    target: str = ""
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    status: AgentStatus = AgentStatus.CREATED
    history: list = field(default_factory=list)


class Agent(ABC):
    """A named, addressable agent able to execute a goal using capabilities
    and memory. Lifecycle is coordinated by the kernel AgentManager."""

    name: str = "base"

    def __init__(self, kernel=None):
        self.kernel = kernel
        self.logger = logging.getLogger(f"buster.agents.{self.name}")

    @abstractmethod
    def run(self, target: str, **kwargs) -> AgentRun:
        """Pursue ``target`` and return the resulting AgentRun."""

    def step(self, run: AgentRun, action: str, **kwargs) -> Any:
        """Record one step of an ongoing run (default no-op recording)."""
        run.history.append({"ts": time.time(), "action": action, **kwargs})
        return None
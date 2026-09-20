"""Kernel core for Buster OS.

The kernel owns the lifecycle of the whole environment: it initialises the
single EventRouter, Scheduler, Permissions, WorldModel, AgentManager and
Audit subsystems, starts them in a deterministic order and tears them down
on shutdown. There is exactly one Kernel instance per process.
"""

import logging
import os
from typing import Optional

from buster.config import Config
from buster.kernel.agent_manager import AgentManager
from buster.kernel.audit import Audit
from buster.kernel.event_router import EventRouter
from buster.kernel.permissions import Permissions
from buster.kernel.scheduler import Scheduler
from buster.kernel.world_model import WorldModel
from buster.logging import setup_logging
from buster.version import get_version


class Kernel:
    """Lifecycle controller owning all core subsystems."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.state = "created"

        self.event_router = EventRouter()
        self.scheduler = Scheduler()
        self.permissions = Permissions()
        self.world_model = WorldModel(event_router=self.event_router)
        self.agent_manager = AgentManager(event_router=self.event_router)

        log_dir = os.path.join(self.config.get("install_path", os.path.expanduser("~/.buster/")), "logs")
        self.audit = Audit(log_dir)
        self.logger = logging.getLogger("buster.kernel.core")

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self.state == "running":
            return
        self.state = "starting"
        self.logger.info("Buster OS kernel %s starting", get_version())

        setup_logging(os.path.join(self.config.get("install_path", os.path.expanduser("~/.buster/")), "logs"),
                      self.config.get("logging_level", "INFO"))

        self.event_router.start()
        self.world_model.set_fact("buster.version", get_version())
        self.world_model.component_status("kernel", "starting")
        self.scheduler.start()
        self.world_model.component_status("event_router", "running")
        self.world_model.component_status("scheduler", "running")
        self.world_model.component_status("kernel", "running")

        self.state = "running"
        self.event_router.emit("kernel.started", {"version": get_version()})
        self.audit.record("kernel.start", "kernel", {"version": get_version()})
        self.logger.info("Buster OS kernel running.")

    def stop(self) -> None:
        if self.state == "stopped":
            return
        self.state = "stopping"
        self.logger.info("Buster OS kernel stopping")

        self.agent_manager.shutdown_all()
        self.scheduler.stop()

        self.world_model.component_status("kernel", "stopped")
        self.audit.record("kernel.stop", "kernel")
        self.event_router.stop()
        self.state = "stopped"
        self.logger.info("Buster OS kernel stopped.")

    # -- convenience accessors ----------------------------------------

    def status(self) -> dict:
        return {
            "state": self.state,
            "version": get_version(),
            "event_router_running": self.event_router.running,
            "scheduler_running": self.scheduler.running,
            "agents": [a.name for a in self.agent_manager.list_agents()],
            "jobs": [{"name": j.name, "status": j.status.value} for j in self.scheduler.list_jobs()],
        }

    def require(self, action: str, scope: Optional[str] = None,
                context: Optional[dict] = None) -> None:
        """Gate an action through the kernel permission system."""
        self.permissions.require(action, scope, context)
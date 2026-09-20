"""Elevation manager for sensitive actions.

Actions that mutate security-relevant state (grants, config, deletes,
process kills) may be gated behind an elevation decision. The default
policy is deny unless an approval callback grants it.
"""

import logging
from typing import Callable, Optional

ApprovalCallback = Callable[[str, dict], bool]

#: Actions considered sensitive by default and always routed to elevation.
SENSITIVE_DEFAULT = {
    "fs.delete",
    "config.set",
    "permission.grant",
    "permission.deny",
    "process.kill",
}


class ElevationManager:
    """Decides whether sensitive actions may run elevated."""

    def __init__(self, sensitive: Optional[set] = None,
                 approval: Optional[ApprovalCallback] = None):
        self._sensitive = set(sensitive) if sensitive is not None else set(SENSITIVE_DEFAULT)
        self._approval = approval
        self.logger = logging.getLogger("buster.security.elevation")

    def requires_elevation(self, action: str) -> bool:
        return action in self._sensitive

    def mark_sensitive(self, action: str, sensitive: bool = True) -> None:
        if sensitive:
            self._sensitive.add(action)
        else:
            self._sensitive.discard(action)

    def approve(self, action: str, context: Optional[dict] = None) -> bool:
        """Request approval to elevate. Denied by default."""
        context = context or {}
        if self._approval is None:
            self.logger.warning("Elevation requested for '%s' but no approver set", action)
            return False
        try:
            return bool(self._approval(action, context))
        except Exception:  # noqa: BLE001
            self.logger.exception("Elevation approver raised")
            return False

    def approve_scripted(self, allowlist: Optional[set] = None) -> ApprovalCallback:
        """Build an approval callback honouring a static allowlist."""
        allowed = set(allowlist or ())
        return lambda action, ctx: action in allowed
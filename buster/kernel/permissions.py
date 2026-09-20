"""Permission system for Buster OS.

Every capability and agent action is gated through permission checks.
Decisions are allow/deny by default with an optional prompting hook for
interactive approval. Rules may be persisted via a callback so grants
survive process restarts.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

PermissionEvaluator = Callable[[str, Optional[str], dict], bool]
PersistHook = Callable[[list[dict]], None]


class PermissionDenied(PermissionError):
    """Raised when a requested action is denied by the permission system."""


@dataclass
class PermissionRule:
    action: str
    allow: bool
    scope: Optional[str] = None
    note: str = ""


@dataclass
class PermissionDecision:
    action: str
    allowed: bool
    reason: str = ""
    source: str = "policy"

    def __bool__(self) -> bool:
        return self.allowed


class Permissions:
    """Policy store and enforcement point for Buster actions."""

    def __init__(self, persist: Optional[PersistHook] = None):
        self._rules: list[PermissionRule] = []
        self._evaluators: list[PermissionEvaluator] = []
        self._persist = persist
        self.logger = logging.getLogger("buster.kernel.permissions")

    def grant(self, action: str, scope: Optional[str] = None, note: str = "") -> None:
        self._rules.append(PermissionRule(action, True, scope, note))
        self.logger.info("Granted permission '%s'", action)
        self._notify()

    def deny(self, action: str, scope: Optional[str] = None, note: str = "") -> None:
        self._rules.append(PermissionRule(action, False, scope, note))
        self.logger.info("Denied permission '%s'", action)
        self._notify()

    def from_rules(self, rules: list[dict]) -> None:
        """Replace current rules from a persisted representation."""
        self._rules.clear()
        for row in rules or []:
            self._rules.append(PermissionRule(
                action=row.get("action", ""),
                allow=bool(row.get("allow", False)),
                scope=row.get("scope"),
                note=row.get("note", ""),
            ))

    def to_rules(self) -> list[dict]:
        return [
            {"action": r.action, "allow": r.allow, "scope": r.scope, "note": r.note}
            for r in self._rules
        ]

    def _notify(self) -> None:
        if self._persist is not None:
            try:
                self._persist(self.to_rules())
            except Exception:  # noqa: BLE001
                self.logger.exception("Failed to persist permission rules")

    def register_evaluator(self, evaluator: PermissionEvaluator) -> None:
        """Register a callable ``evaluator(action, scope, context) -> bool``.

        Evaluators run in registration order after static rules; if any
        returns True the action is allowed, if any returns False it is
        denied. Returning None lets later evaluators decide.
        """
        self._evaluators.append(evaluator)

    def check(self, action: str, scope: Optional[str] = None,
              context: Optional[dict] = None) -> PermissionDecision:
        context = context or {}

        def applies(rule: PermissionRule) -> bool:
            return not rule.scope or (scope is not None and rule.scope == scope)

        rule_matches = [r for r in self._rules if r.action == action and applies(r)]
        for rule in rule_matches:
            if not rule.allow:
                return PermissionDecision(action, False, rule.note, "policy")
        for rule in rule_matches:
            if rule.allow:
                return PermissionDecision(action, True, rule.note, "policy")

        for evaluator in self._evaluators:
            try:
                result = evaluator(action, scope, context)
            except Exception:  # noqa: BLE001 - an evaluator must not break the gate
                self.logger.exception("Evaluator error for action '%s'", action)
                continue
            if result is True:
                return PermissionDecision(action, True, "evaluator approved", "evaluator")
            if result is False:
                return PermissionDecision(action, False, "evaluator denied", "evaluator")

        return PermissionDecision(action, False, "denied by default", "default")

    def require(self, action: str, scope: Optional[str] = None,
                context: Optional[dict] = None) -> None:
        decision = self.check(action, scope, context)
        if not decision.allowed:
            raise PermissionDenied(
                f"Permission denied for action '{action}': {decision.reason}"
            )

    def clear(self) -> None:
        self._rules.clear()
        self._evaluators.clear()
        self._notify()
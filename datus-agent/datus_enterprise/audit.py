"""Audit helpers for downstream enterprise routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AuditEvent as CoreAuditEvent


@dataclass(frozen=True)
class AuditEvent:
    """Minimal audit event shape used by enterprise route wrappers."""

    action: str
    resource_type: str
    resource_id: Optional[str]
    decision: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


async def audit_decision(ctx: AppContext, event: AuditEvent) -> None:
    """Record an authorization or mutation decision."""

    from datus.api.enterprise.deps import get_audit_sink

    await get_audit_sink().write(
        CoreAuditEvent(
            user_id=ctx.user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            decision=event.decision,
            reason=event.reason,
            metadata=dict(event.metadata),
        )
    )

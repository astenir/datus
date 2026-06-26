"""Audit hook abstractions for enterprise routes.

The default implementation is intentionally no-op so local/open-source mode
keeps its current behavior. Production enterprise deployments should replace
this module-level sink with a durable implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from datus.api.auth.context import AppContext


@dataclass(frozen=True)
class AuditEvent:
    """Minimal audit event shape used by enterprise route wrappers."""

    action: str
    resource_type: str
    resource_id: Optional[str]
    decision: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NoopAuditSink:
    """Local-compatible audit sink."""

    async def record(self, ctx: AppContext, event: AuditEvent) -> None:  # noqa: ARG002
        return None


_audit_sink: NoopAuditSink = NoopAuditSink()


def get_audit_sink() -> NoopAuditSink:
    return _audit_sink


async def audit_decision(ctx: AppContext, event: AuditEvent) -> None:
    """Record an authorization or mutation decision."""

    await get_audit_sink().record(ctx, event)

"""Stable enterprise extension data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from datus.configuration.agent_config import AgentConfig


@dataclass(frozen=True)
class ResourceRef:
    """Resource being authorized."""

    type: str
    id: str | None = None
    project_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessDecision:
    """Authorization decision returned by enterprise providers."""

    allowed: bool
    reason: str | None = None
    code: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionInput:
    """Request-level config projection input."""

    ctx: Any
    base_config: AgentConfig
    operation: str
    requested_datasource: str | None = None
    requested_catalog: str | None = None
    requested_database: str | None = None
    requested_schema: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionResult:
    """Projected request config and derived security metadata."""

    config: AgentConfig
    principal: dict[str, Any] = field(default_factory=dict)
    datasource_grants: dict[str, Any] = field(default_factory=dict)
    denied_reason: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """Security audit event shape for enterprise extension sinks."""

    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    decision: str
    reason: str | None = None
    request_id: str | None = None
    id: int | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

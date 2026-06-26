"""Local-compatible default enterprise extension implementations."""

from __future__ import annotations

import copy
import os
import sqlite3
from fnmatch import fnmatchcase
from typing import Any

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AccessDecision, AuditEvent, ProjectionInput, ProjectionResult, ResourceRef
from datus.utils.exceptions import DatusException, ErrorCode


class LocalAuthorizationProvider:
    """Default authorization provider for local/open-source mode.

    Missing permissions mean local-compatible allow. If permissions are
    present, checks are evaluated against stable permission keys and glob
    patterns such as ``module.dashboard.*``.
    """

    async def check(self, ctx: AppContext, action: str, resource: ResourceRef) -> AccessDecision:  # noqa: ARG002
        permissions = _context_permissions(ctx)
        if permissions is None:
            return AccessDecision(allowed=True, reason="local-compatible allow")
        if _matches_permission(action, permissions):
            return AccessDecision(allowed=True, reason="permission matched")
        return AccessDecision(allowed=False, reason=f"missing permission {action}", code="PERMISSION_DENIED")

    async def allowed_datasources(self, ctx: AppContext) -> dict[str, Any]:
        return dict(ctx.datasource_grants or {})


class PassthroughConfigProjector:
    """Clone AgentConfig without applying enterprise datasource grants."""

    async def project(self, request: ProjectionInput) -> ProjectionResult:
        projected = copy.deepcopy(request.base_config)
        principal = dict(request.ctx.principal or {})
        if request.requested_datasource:
            if request.requested_datasource not in projected.services.datasources:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"Datasource '{request.requested_datasource}' not found in services.datasources.",
                )
            projected.current_datasource = request.requested_datasource
            principal.setdefault("datasource", request.requested_datasource)
        projected.principal = principal
        return ProjectionResult(
            config=projected,
            principal=principal,
            datasource_grants=dict(request.ctx.datasource_grants or {}),
        )


class InMemorySessionOwnerStore:
    """Process-local session owner store for tests and local mode."""

    def __init__(self) -> None:
        self._owners: dict[tuple[str, str], str] = {}

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        self._owners[(project_id, session_id)] = user_id

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        return self._owners.get((project_id, session_id))

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        self._owners.pop((project_id, session_id), None)

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        return [
            session_id
            for (stored_project, session_id), owner in self._owners.items()
            if stored_project == project_id and owner == user_id
        ]


class SqliteSessionOwnerStore:
    """SQLite-backed ``session_owners`` metadata index.

    This is a small default implementation for single-node deployments and
    tests. Enterprise deployments can replace it with Postgres/Redis-backed
    metadata through ``enterprise.session_owner_store.class``.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_owners (project_id, session_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id, session_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (project_id, session_id, user_id),
            )
            conn.commit()

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM session_owners WHERE project_id = ? AND session_id = ?",
                (project_id, session_id),
            ).fetchone()
        return str(row[0]) if row else None

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM session_owners WHERE project_id = ? AND session_id = ?",
                (project_id, session_id),
            )
            conn.commit()

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id
                FROM session_owners
                WHERE project_id = ? AND user_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id, user_id),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_owners (
                    project_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_owners_user
                ON session_owners (project_id, user_id, updated_at)
                """
            )
            conn.commit()


class NoopAuditSink:
    """No-op audit sink for local/open-source mode."""

    async def write(self, event: AuditEvent) -> None:  # noqa: ARG002
        return None


def _context_permissions(ctx: AppContext) -> list[str] | None:
    if ctx.permissions:
        return sorted(ctx.permissions)
    raw = ctx.principal.get("permissions")
    if raw is None:
        return None
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return []


def _matches_permission(action: str, permissions: list[str]) -> bool:
    return any(permission == "*" or fnmatchcase(action, permission) for permission in permissions)

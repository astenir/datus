"""Local-compatible default enterprise extension implementations."""

from __future__ import annotations

import copy
import os
import sqlite3
from datetime import datetime, timezone
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


class InMemoryEnterpriseUserStore:
    """Process-local enterprise user metadata store for tests and local mode."""

    def __init__(self) -> None:
        self._users: dict[str, dict[str, Any]] = {}

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        users = [
            _copy_user_record(record)
            for record in self._users.values()
            if enabled is None or bool(record["enabled"]) is enabled
        ]
        return sorted(users, key=lambda record: str(record["user_id"]))

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        record = self._users.get(user_id)
        return _copy_user_record(record) if record is not None else None

    async def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        email: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        existing = self._users.get(user_id)
        now = _sqlite_now()
        created_at = str(existing.get("created_at")) if existing else now
        record = {
            "user_id": user_id,
            "display_name": display_name,
            "email": email,
            "enabled": bool(enabled),
            "created_at": created_at,
            "updated_at": now,
        }
        self._users[user_id] = record
        return _copy_user_record(record)

    async def set_user_enabled(self, user_id: str, enabled: bool) -> dict[str, Any] | None:
        record = self._users.get(user_id)
        if record is None:
            return None
        record = dict(record)
        record["enabled"] = bool(enabled)
        record["updated_at"] = _sqlite_now()
        self._users[user_id] = record
        return _copy_user_record(record)


class SqliteEnterpriseUserStore:
    """SQLite-backed enterprise user metadata store for single-node deployments."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        if enabled is None:
            query = """
                SELECT user_id, display_name, email, enabled, created_at, updated_at
                FROM enterprise_users
                ORDER BY user_id ASC
                """
            params: tuple[Any, ...] = ()
        else:
            query = """
                SELECT user_id, display_name, email, enabled, created_at, updated_at
                FROM enterprise_users
                WHERE enabled = ?
                ORDER BY user_id ASC
                """
            params = (1 if enabled else 0,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_user_record_from_row(row) for row in rows]

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, display_name, email, enabled, created_at, updated_at
                FROM enterprise_users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return _user_record_from_row(row) if row else None

    async def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        email: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_users (user_id, display_name, email, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    email = excluded.email,
                    enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, display_name, email, 1 if enabled else 0),
            )
            conn.commit()
        record = await self.get_user(user_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise user.")
        return record

    async def set_user_enabled(self, user_id: str, enabled: bool) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE enterprise_users
                SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (1 if enabled else 0, user_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_user(user_id)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    email TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_users_enabled
                ON enterprise_users (enabled, user_id)
                """
            )
            conn.commit()


class InMemoryEnterpriseRoleStore:
    """Process-local enterprise role metadata store for tests and local mode."""

    def __init__(self) -> None:
        self._roles: dict[str, dict[str, Any]] = {}
        self._user_roles: dict[str, set[str]] = {}

    async def list_roles(self) -> list[dict[str, Any]]:
        roles = [_copy_role_record(record) for record in self._roles.values()]
        return sorted(roles, key=lambda record: str(record["role_id"]))

    async def get_role(self, role_id: str) -> dict[str, Any] | None:
        record = self._roles.get(role_id)
        return _copy_role_record(record) if record is not None else None

    async def upsert_role(
        self,
        *,
        role_id: str,
        name: str,
        description: str | None = None,
        permissions: list[str] | None = None,
        built_in: bool = False,
    ) -> dict[str, Any]:
        existing = self._roles.get(role_id)
        now = _sqlite_now()
        created_at = str(existing.get("created_at")) if existing else now
        record = {
            "role_id": role_id,
            "name": name,
            "description": description,
            "permissions": _normalized_permissions(permissions or []),
            "built_in": bool(built_in),
            "created_at": created_at,
            "updated_at": now,
        }
        self._roles[role_id] = record
        return _copy_role_record(record)

    async def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict[str, Any] | None:
        record = self._roles.get(role_id)
        if record is None:
            return None
        record = dict(record)
        record["permissions"] = _normalized_permissions(permissions)
        record["updated_at"] = _sqlite_now()
        self._roles[role_id] = record
        return _copy_role_record(record)

    async def list_user_roles(self, user_id: str) -> list[str]:
        return sorted(self._user_roles.get(user_id, set()))

    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> list[str]:
        normalized = _normalized_role_ids(role_ids)
        missing_role_ids = [role_id for role_id in normalized if role_id not in self._roles]
        if missing_role_ids:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Role not found: {missing_role_ids[0]}.",
            )
        if normalized:
            self._user_roles[user_id] = set(normalized)
        else:
            self._user_roles.pop(user_id, None)
        return normalized

    async def list_role_users(self, role_id: str) -> list[str]:
        return sorted(user_id for user_id, role_ids in self._user_roles.items() if role_id in role_ids)

    async def delete_role(self, role_id: str) -> bool:
        if await self.list_role_users(role_id):
            return False
        return self._roles.pop(role_id, None) is not None


class SqliteEnterpriseRoleStore:
    """SQLite-backed enterprise role metadata store for single-node deployments."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_roles(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role_id, name, description, built_in, created_at, updated_at
                FROM enterprise_roles
                ORDER BY role_id ASC
                """
            ).fetchall()
            return [_role_record_from_row(conn, row) for row in rows]

    async def get_role(self, role_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT role_id, name, description, built_in, created_at, updated_at
                FROM enterprise_roles
                WHERE role_id = ?
                """,
                (role_id,),
            ).fetchone()
            return _role_record_from_row(conn, row) if row else None

    async def upsert_role(
        self,
        *,
        role_id: str,
        name: str,
        description: str | None = None,
        permissions: list[str] | None = None,
        built_in: bool = False,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_roles (role_id, name, description, built_in, created_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(role_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    built_in = excluded.built_in,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (role_id, name, description, 1 if built_in else 0),
            )
            _replace_role_permissions(conn, role_id, permissions or [])
            conn.commit()
        record = await self.get_role(role_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise role.")
        return record

    async def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict[str, Any] | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM enterprise_roles WHERE role_id = ?",
                (role_id,),
            ).fetchone()
            if not exists:
                return None
            _replace_role_permissions(conn, role_id, permissions)
            conn.execute(
                """
                UPDATE enterprise_roles
                SET updated_at = CURRENT_TIMESTAMP
                WHERE role_id = ?
                """,
                (role_id,),
            )
            conn.commit()
        return await self.get_role(role_id)

    async def delete_role(self, role_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            assigned = conn.execute(
                "SELECT 1 FROM enterprise_user_roles WHERE role_id = ? LIMIT 1",
                (role_id,),
            ).fetchone()
            if assigned:
                return False
            conn.execute("DELETE FROM enterprise_role_permissions WHERE role_id = ?", (role_id,))
            cursor = conn.execute("DELETE FROM enterprise_roles WHERE role_id = ?", (role_id,))
            conn.commit()
        return cursor.rowcount > 0

    async def list_user_roles(self, user_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role_id
                FROM enterprise_user_roles
                WHERE user_id = ?
                ORDER BY role_id ASC
                """,
                (user_id,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> list[str]:
        normalized = _normalized_role_ids(role_ids)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing_rows = (
                conn.execute(
                    f"""
                SELECT role_id
                FROM enterprise_roles
                WHERE role_id IN ({",".join("?" for _ in normalized)})
                """,
                    tuple(normalized),
                ).fetchall()
                if normalized
                else []
            )
            existing_role_ids = {str(row[0]) for row in existing_rows}
            missing_role_ids = [role_id for role_id in normalized if role_id not in existing_role_ids]
            if missing_role_ids:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"Role not found: {missing_role_ids[0]}.",
                )
            conn.execute("DELETE FROM enterprise_user_roles WHERE user_id = ?", (user_id,))
            conn.executemany(
                """
                INSERT INTO enterprise_user_roles (user_id, role_id, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                [(user_id, role_id) for role_id in normalized],
            )
            conn.commit()
        return normalized

    async def list_role_users(self, role_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id
                FROM enterprise_user_roles
                WHERE role_id = ?
                ORDER BY user_id ASC
                """,
                (role_id,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_roles (
                    role_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    built_in INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_role_permissions (
                    role_id TEXT NOT NULL,
                    permission_key TEXT NOT NULL,
                    PRIMARY KEY (role_id, permission_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_user_roles (
                    user_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, role_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_user_roles_role
                ON enterprise_user_roles (role_id, user_id)
                """
            )
            conn.commit()


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

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return owner metadata for admin session management."""

        records = [
            {
                "project_id": stored_project,
                "session_id": session_id,
                "user_id": owner,
                "created_at": None,
                "updated_at": None,
            }
            for (stored_project, session_id), owner in self._owners.items()
            if stored_project == project_id and (user_id is None or owner == user_id)
        ]
        return sorted(records, key=lambda record: (str(record["user_id"]), str(record["session_id"])))


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

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return owner metadata for admin session management."""

        params: tuple[str, ...]
        if user_id is None:
            query = """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """
            params = (project_id,)
        else:
            query = """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ? AND user_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """
            params = (project_id, user_id)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "project_id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

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


def _sqlite_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _copy_user_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(record["user_id"]),
        "display_name": _optional_str(record.get("display_name")),
        "email": _optional_str(record.get("email")),
        "enabled": bool(record.get("enabled")),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _user_record_from_row(row) -> dict[str, Any]:
    return {
        "user_id": str(row[0]),
        "display_name": _optional_str(row[1]),
        "email": _optional_str(row[2]),
        "enabled": bool(row[3]),
        "created_at": _optional_str(row[4]),
        "updated_at": _optional_str(row[5]),
    }


def _copy_role_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "role_id": str(record["role_id"]),
        "name": str(record["name"]),
        "description": _optional_str(record.get("description")),
        "permissions": _normalized_permissions(record.get("permissions") or []),
        "built_in": bool(record.get("built_in")),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _role_record_from_row(conn: sqlite3.Connection, row) -> dict[str, Any]:
    return {
        "role_id": str(row[0]),
        "name": str(row[1]),
        "description": _optional_str(row[2]),
        "permissions": _role_permissions(conn, str(row[0])),
        "built_in": bool(row[3]),
        "created_at": _optional_str(row[4]),
        "updated_at": _optional_str(row[5]),
    }


def _role_permissions(conn: sqlite3.Connection, role_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT permission_key
        FROM enterprise_role_permissions
        WHERE role_id = ?
        ORDER BY permission_key ASC
        """,
        (role_id,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _replace_role_permissions(conn: sqlite3.Connection, role_id: str, permissions: list[str]) -> None:
    conn.execute("DELETE FROM enterprise_role_permissions WHERE role_id = ?", (role_id,))
    conn.executemany(
        """
        INSERT INTO enterprise_role_permissions (role_id, permission_key)
        VALUES (?, ?)
        """,
        [(role_id, permission) for permission in _normalized_permissions(permissions)],
    )


def _normalized_permissions(permissions: Any) -> list[str]:
    if not isinstance(permissions, list):
        return []
    normalized = {
        permission.strip() for permission in permissions if isinstance(permission, str) and permission.strip()
    }
    return sorted(normalized)


def _normalized_role_ids(role_ids: Any) -> list[str]:
    if not isinstance(role_ids, list):
        return []
    normalized = {role_id.strip() for role_id in role_ids if isinstance(role_id, str) and role_id.strip()}
    return sorted(normalized)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None

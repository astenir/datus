"""Local-compatible default enterprise extension implementations."""

from __future__ import annotations

import copy
import json
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


class InMemoryEnterpriseDatasourceGrantStore:
    """Process-local datasource grant metadata store for tests and local mode."""

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        records = [
            _copy_datasource_grant_record(record)
            for record in self._grants.values()
            if _grant_matches_filters(
                record,
                subject_type=subject_type,
                subject_id=subject_id,
                datasource_key=datasource_key,
            )
        ]
        return sorted(
            records,
            key=lambda record: (
                str(record["subject_type"]),
                str(record["subject_id"]),
                str(record["datasource_key"]),
            ),
        )

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        record = self._grants.get((subject_type, subject_id, datasource_key))
        return _copy_datasource_grant_record(record) if record is not None else None

    async def put_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
        effect: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _sqlite_now()
        key = (subject_type, subject_id, datasource_key)
        existing = self._grants.get(key)
        record = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
            "effect": _normalized_grant_effect(effect),
            "scope": _normalized_grant_scope(scope),
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._grants[key] = record
        return _copy_datasource_grant_record(record)

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        return self._grants.pop((subject_type, subject_id, datasource_key), None) is not None


class InMemoryEnterpriseQuotaStore:
    """Process-local quota metadata and usage store for tests and local mode."""

    def __init__(self) -> None:
        self._quotas: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._usage: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def list_quotas(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        records = [
            _copy_quota_record(record)
            for record in self._quotas.values()
            if _quota_filter_matches(record, subject_type=subject_type, subject_id=subject_id, resource=resource)
        ]
        return sorted(records, key=lambda record: (record["subject_type"], record["subject_id"], record["resource"]))

    async def put_quota(
        self,
        *,
        subject_type: str,
        subject_id: str,
        resource: str,
        limit: int,
        window_seconds: int,
        enabled: bool = True,
    ) -> dict[str, Any]:
        now = _sqlite_now()
        key = (subject_type, subject_id, resource)
        existing = self._quotas.get(key)
        record = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "resource": resource,
            "limit": int(limit),
            "window_seconds": int(window_seconds),
            "enabled": bool(enabled),
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._quotas[key] = record
        return _copy_quota_record(record)

    async def list_usage(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        usage = [
            copy.deepcopy(record)
            for record in self._usage.values()
            if _quota_filter_matches(record, subject_type=subject_type, subject_id=subject_id, resource=resource)
        ]
        return sorted(usage, key=lambda record: (record["subject_type"], record["subject_id"], record["resource"]))


class InMemoryEnterpriseSecretStore:
    """Process-local secret reference store for tests and local mode."""

    def __init__(self) -> None:
        self._secrets: dict[str, dict[str, Any]] = {}

    async def list_secrets(self, *, prefix: str | None = None) -> list[dict[str, Any]]:
        records = [
            _copy_secret_record(record)
            for record in self._secrets.values()
            if prefix is None or str(record["name"]).startswith(prefix)
        ]
        return sorted(records, key=lambda record: record["name"])

    async def get_secret(self, name: str) -> dict[str, Any] | None:
        record = self._secrets.get(name)
        return _copy_secret_record(record) if record is not None else None

    async def put_secret(
        self,
        *,
        name: str,
        provider: str,
        reference: str,
        description: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        now = _sqlite_now()
        existing = self._secrets.get(name)
        record = {
            "name": name,
            "provider": provider,
            "reference": reference,
            "description": description,
            "enabled": bool(enabled),
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._secrets[name] = record
        return _copy_secret_record(record)

    async def delete_secret(self, name: str) -> bool:
        return self._secrets.pop(name, None) is not None


class SqliteEnterpriseDatasourceGrantStore:
    """SQLite-backed datasource grant metadata store for single-node deployments."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if subject_type is not None:
            where.append("subject_type = ?")
            params.append(subject_type)
        if subject_id is not None:
            where.append("subject_id = ?")
            params.append(subject_id)
        if datasource_key is not None:
            where.append("datasource_key = ?")
            params.append(datasource_key)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        query = f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [_datasource_grant_record_from_row(row) for row in rows]

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
                FROM enterprise_datasource_grants
                WHERE subject_type = ? AND subject_id = ? AND datasource_key = ?
                """,
                (subject_type, subject_id, datasource_key),
            ).fetchone()
        return _datasource_grant_record_from_row(row) if row else None

    async def put_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
        effect: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_effect = _normalized_grant_effect(effect)
        normalized_scope = _normalized_grant_scope(scope)
        scope_json = json.dumps(normalized_scope, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_datasource_grants (
                    subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(subject_type, subject_id, datasource_key) DO UPDATE SET
                    effect = excluded.effect,
                    scope_json = excluded.scope_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (subject_type, subject_id, datasource_key, normalized_effect, scope_json),
            )
            conn.commit()
        record = await self.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist datasource grant.")
        return record

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM enterprise_datasource_grants
                WHERE subject_type = ? AND subject_id = ? AND datasource_key = ?
                """,
                (subject_type, subject_id, datasource_key),
            )
            conn.commit()
        return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    datasource_key TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    scope_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (subject_type, subject_id, datasource_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_datasource_grants_datasource
                ON enterprise_datasource_grants (datasource_key, subject_type, subject_id)
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


def _copy_datasource_grant_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject_type": str(record["subject_type"]),
        "subject_id": str(record["subject_id"]),
        "datasource_key": str(record["datasource_key"]),
        "effect": _normalized_grant_effect(record.get("effect", "allow")),
        "scope": copy.deepcopy(_normalized_grant_scope(record.get("scope"))),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _copy_quota_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject_type": str(record["subject_type"]),
        "subject_id": str(record["subject_id"]),
        "resource": str(record["resource"]),
        "limit": int(record["limit"]),
        "window_seconds": int(record["window_seconds"]),
        "enabled": bool(record["enabled"]),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _copy_secret_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(record["name"]),
        "provider": str(record["provider"]),
        "reference": str(record["reference"]),
        "description": _optional_str(record.get("description")),
        "enabled": bool(record["enabled"]),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _quota_filter_matches(
    record: dict[str, Any],
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    resource: str | None = None,
) -> bool:
    if subject_type is not None and record.get("subject_type") != subject_type:
        return False
    if subject_id is not None and record.get("subject_id") != subject_id:
        return False
    if resource is not None and record.get("resource") != resource:
        return False
    return True


def _datasource_grant_record_from_row(row) -> dict[str, Any]:
    return {
        "subject_type": str(row[0]),
        "subject_id": str(row[1]),
        "datasource_key": str(row[2]),
        "effect": _normalized_grant_effect(row[3]),
        "scope": _load_grant_scope_json(row[4]),
        "created_at": _optional_str(row[5]),
        "updated_at": _optional_str(row[6]),
    }


def _grant_matches_filters(
    record: dict[str, Any],
    *,
    subject_type: str | None,
    subject_id: str | None,
    datasource_key: str | None,
) -> bool:
    return (
        (subject_type is None or record["subject_type"] == subject_type)
        and (subject_id is None or record["subject_id"] == subject_id)
        and (datasource_key is None or record["datasource_key"] == datasource_key)
    )


def _normalized_grant_effect(effect: Any) -> str:
    normalized = str(effect).strip().lower()
    if normalized not in {"allow", "deny"}:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Datasource grant effect must be allow or deny.")
    return normalized


def _normalized_grant_scope(scope: Any) -> dict[str, Any]:
    if scope is None:
        return {}
    if not isinstance(scope, dict):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Datasource grant scope must be a mapping.")
    allowed_keys = {"allow_catalog", "allow_sql", "catalogs", "databases", "schemas", "tables"}
    unknown_keys = sorted(set(scope) - allowed_keys)
    if unknown_keys:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Unsupported datasource grant scope key: {unknown_keys[0]}.",
        )

    normalized: dict[str, Any] = {}
    for key in ("allow_catalog", "allow_sql"):
        if key not in scope:
            continue
        if not isinstance(scope[key], bool):
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource grant scope.{key} must be a boolean.",
            )
        normalized[key] = scope[key]

    for key in ("catalogs", "databases", "schemas", "tables"):
        if key not in scope or scope[key] is None:
            continue
        values = scope[key]
        if not isinstance(values, list):
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource grant scope.{key} must be a list of strings.",
            )
        normalized[key] = _normalized_grant_scope_patterns(values, key)
    return normalized


def _normalized_grant_scope_patterns(values: list[Any], key: str) -> list[str]:
    if len(values) > 200:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Datasource grant scope.{key} cannot contain more than 200 patterns.",
        )
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource grant scope.{key} must contain only strings.",
            )
        candidate = value.strip()
        if candidate != value or not candidate or len(candidate) > 256:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Invalid datasource grant scope.{key} pattern.",
            )
        normalized.add(candidate)
    return sorted(normalized)


def _load_grant_scope_json(raw_scope: Any) -> dict[str, Any]:
    if raw_scope in (None, ""):
        return {}
    try:
        loaded = json.loads(str(raw_scope))
    except json.JSONDecodeError as e:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid datasource grant scope JSON.") from e
    return _normalized_grant_scope(loaded)


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

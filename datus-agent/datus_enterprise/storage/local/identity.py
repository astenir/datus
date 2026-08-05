"""Local SQLite and in-memory enterprise identity stores."""

from __future__ import annotations

import copy
import os
import sqlite3
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.local.common import (
    _copy_role_record,
    _copy_user_record,
    _empty_chat_preference,
    _ensure_sqlite_columns,
    _normalized_permissions,
    _normalized_role_ids,
    _offload_sqlite_async_methods,
    _replace_role_permissions,
    _role_record_from_row,
    _sqlite_now,
    _user_record_from_row,
)


class InMemoryEnterpriseUserStore:
    """Process-local enterprise user metadata store for tests and local mode."""

    def __init__(self) -> None:
        self._users: dict[str, dict[str, Any]] = {}
        self._chat_preferences: dict[str, dict[str, Any]] = {}

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        users = [
            _copy_user_record(record)
            for record in self._users.values()
            if enabled is None or bool(record["enabled"]) is enabled
        ]
        return sorted(users, key=lambda record: str(record["user_id"]))

    async def list_users_page(
        self,
        *,
        enabled: bool | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        users = await self.list_users(enabled=enabled)
        query = (search or "").strip().casefold()
        if query:
            users = [
                record
                for record in users
                if any(
                    query in str(record.get(field) or "").casefold()
                    for field in ("user_id", "display_name", "email", "external_user_id", "department", "title")
                )
            ]
        return users[offset : offset + limit]

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
        external_user_id: str | None = None,
        department: str | None = None,
        title: str | None = None,
        last_seen_at: str | None = None,
    ) -> dict[str, Any]:
        existing = self._users.get(user_id)
        now = _sqlite_now()
        created_at = str(existing.get("created_at")) if existing else now
        record = {
            "user_id": user_id,
            "display_name": display_name,
            "email": email,
            "enabled": bool(enabled),
            "external_user_id": external_user_id,
            "department": department,
            "title": title,
            "last_seen_at": last_seen_at,
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

    async def get_chat_preference(self, user_id: str) -> dict[str, Any]:
        record = self._chat_preferences.get(user_id)
        return copy.deepcopy(record) if record is not None else _empty_chat_preference(user_id)

    async def put_chat_preference(self, *, user_id: str, default_agent_id: str | None) -> dict[str, Any]:
        existing = self._chat_preferences.get(user_id)
        now = _sqlite_now()
        record = {
            "user_id": user_id,
            "default_agent_id": default_agent_id,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        self._chat_preferences[user_id] = record
        return copy.deepcopy(record)


@_offload_sqlite_async_methods
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
                SELECT
                    user_id,
                    display_name,
                    email,
                    enabled,
                    external_user_id,
                    department,
                    title,
                    last_seen_at,
                    created_at,
                    updated_at
                FROM enterprise_users
                ORDER BY user_id ASC
                """
            params: tuple[Any, ...] = ()
        else:
            query = """
                SELECT
                    user_id,
                    display_name,
                    email,
                    enabled,
                    external_user_id,
                    department,
                    title,
                    last_seen_at,
                    created_at,
                    updated_at
                FROM enterprise_users
                WHERE enabled = ?
                ORDER BY user_id ASC
                """
            params = (1 if enabled else 0,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_user_record_from_row(row) for row in rows]

    async def list_users_page(
        self,
        *,
        enabled: bool | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if enabled is not None:
            filters.append("u.enabled = ?")
            params.append(1 if enabled else 0)
        if search and search.strip():
            pattern = f"%{search.strip().casefold()}%"
            filters.append(
                """(
                    lower(u.user_id) LIKE ?
                    OR lower(COALESCE(u.display_name, '')) LIKE ?
                    OR lower(COALESCE(u.email, '')) LIKE ?
                    OR lower(COALESCE(u.external_user_id, '')) LIKE ?
                    OR lower(COALESCE(u.department, '')) LIKE ?
                    OR lower(COALESCE(u.title, '')) LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM enterprise_user_roles ur
                        WHERE ur.user_id = u.user_id AND lower(ur.role_id) LIKE ?
                    )
                )"""
            )
            params.extend([pattern] * 7)
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend((int(limit), int(offset)))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT u.user_id, u.display_name, u.email, u.enabled, u.external_user_id, u.department, u.title,
                       u.last_seen_at, u.created_at, u.updated_at
                FROM enterprise_users u
                {where_sql}
                ORDER BY u.user_id ASC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        return [_user_record_from_row(row) for row in rows]

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    user_id,
                    display_name,
                    email,
                    enabled,
                    external_user_id,
                    department,
                    title,
                    last_seen_at,
                    created_at,
                    updated_at
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
        external_user_id: str | None = None,
        department: str | None = None,
        title: str | None = None,
        last_seen_at: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_users (
                    user_id,
                    display_name,
                    email,
                    enabled,
                    external_user_id,
                    department,
                    title,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    email = excluded.email,
                    enabled = excluded.enabled,
                    external_user_id = excluded.external_user_id,
                    department = excluded.department,
                    title = excluded.title,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, display_name, email, 1 if enabled else 0, external_user_id, department, title, last_seen_at),
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

    async def get_chat_preference(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, default_agent_id, created_at, updated_at
                FROM enterprise_user_chat_preferences
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row else _empty_chat_preference(user_id)

    async def put_chat_preference(self, *, user_id: str, default_agent_id: str | None) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_user_chat_preferences (
                    user_id, default_agent_id, created_at, updated_at
                )
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    default_agent_id = excluded.default_agent_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, default_agent_id),
            )
            conn.commit()
        return await self.get_chat_preference(user_id)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    email TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    external_user_id TEXT,
                    department TEXT,
                    title TEXT,
                    last_seen_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ensure_sqlite_columns(
                conn,
                "enterprise_users",
                {
                    "external_user_id": "TEXT",
                    "department": "TEXT",
                    "title": "TEXT",
                    "last_seen_at": "TEXT",
                },
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_users_enabled
                ON enterprise_users (enabled, user_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_user_chat_preferences (
                    user_id TEXT PRIMARY KEY,
                    default_agent_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
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


@_offload_sqlite_async_methods
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

"""OceanBase enterprise user and role metadata stores."""

from __future__ import annotations

import asyncio
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.common.normalization import _like_contains_pattern, _normalized_strings
from datus_enterprise.storage.oceanbase.base import _ObStoreBase
from datus_enterprise.storage.oceanbase.records import (
    _chat_preference_record,
    _replace_role_permissions_sync,
    _role_record,
    _user_record,
)
from datus_enterprise.storage.oceanbase.schema import _SCHEMA_SQL


class ObEnterpriseUserStore(_ObStoreBase):
    """OceanBase MySQL-backed enterprise user metadata store."""

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        if enabled is None:
            rows = await self._fetchall(
                """
                SELECT user_id, display_name, email, enabled, external_user_id, department, title,
                       last_seen_at, created_at, updated_at
                FROM enterprise_users
                ORDER BY user_id ASC
                """
            )
        else:
            rows = await self._fetchall(
                """
                SELECT user_id, display_name, email, enabled, external_user_id, department, title,
                       last_seen_at, created_at, updated_at
                FROM enterprise_users
                WHERE enabled = %s
                ORDER BY user_id ASC
                """,
                (bool(enabled),),
            )
        return [_user_record(row) for row in rows]

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
            filters.append("u.enabled = %s")
            params.append(bool(enabled))
        if search and search.strip():
            pattern = _like_contains_pattern(search.strip())
            filters.append(
                """(
                    u.user_id LIKE %s ESCAPE '\\\\'
                    OR COALESCE(u.display_name, '') LIKE %s ESCAPE '\\\\'
                    OR COALESCE(u.email, '') LIKE %s ESCAPE '\\\\'
                    OR COALESCE(u.external_user_id, '') LIKE %s ESCAPE '\\\\'
                    OR COALESCE(u.department, '') LIKE %s ESCAPE '\\\\'
                    OR COALESCE(u.title, '') LIKE %s ESCAPE '\\\\'
                    OR EXISTS (
                        SELECT 1 FROM enterprise_user_roles ur
                        WHERE ur.user_id = u.user_id AND ur.role_id LIKE %s ESCAPE '\\\\'
                    )
                )"""
            )
            params.extend([pattern] * 7)
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend((int(limit), int(offset)))
        rows = await self._fetchall(
            f"""
            SELECT u.user_id, u.display_name, u.email, u.enabled, u.external_user_id, u.department, u.title,
                   u.last_seen_at, u.created_at, u.updated_at
            FROM enterprise_users u
            {where_sql}
            ORDER BY u.user_id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        return [_user_record(row) for row in rows]

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT user_id, display_name, email, enabled, external_user_id, department, title,
                   last_seen_at, created_at, updated_at
            FROM enterprise_users
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return _user_record(row) if row else None

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
        await self._execute(
            """
            INSERT INTO enterprise_users (
                user_id, display_name, email, enabled, external_user_id, department, title,
                last_seen_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                display_name = VALUES(display_name),
                email = VALUES(email),
                enabled = VALUES(enabled),
                external_user_id = VALUES(external_user_id),
                department = VALUES(department),
                title = VALUES(title),
                last_seen_at = VALUES(last_seen_at),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                display_name,
                email,
                bool(enabled),
                external_user_id,
                department,
                title,
                last_seen_at,
            ),
        )
        record = await self.get_user(user_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise user.")
        return record

    async def set_user_enabled(self, user_id: str, enabled: bool) -> dict[str, Any] | None:
        await self._execute(
            """
            UPDATE enterprise_users
            SET enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """,
            (bool(enabled), user_id),
        )
        return await self.get_user(user_id)

    async def get_chat_preference(self, user_id: str) -> dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT user_id, default_agent_id, created_at, updated_at
            FROM enterprise_user_chat_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return _chat_preference_record(row, user_id=user_id)

    async def put_chat_preference(self, *, user_id: str, default_agent_id: str | None) -> dict[str, Any]:
        await self._execute(
            """
            INSERT INTO enterprise_user_chat_preferences (
                user_id, default_agent_id, created_at, updated_at
            )
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                default_agent_id = VALUES(default_agent_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, default_agent_id),
        )
        return await self.get_chat_preference(user_id)


class ObEnterpriseRoleStore(_ObStoreBase):
    """OceanBase MySQL-backed enterprise role metadata and membership store."""

    async def list_roles(self) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT role_id, name, description, built_in, created_at, updated_at
            FROM enterprise_roles
            ORDER BY role_id ASC
            """
        )
        return [await self._role_record_with_permissions(row) for row in rows]

    async def get_role(self, role_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT role_id, name, description, built_in, created_at, updated_at
            FROM enterprise_roles
            WHERE role_id = %s
            """,
            (role_id,),
        )
        return await self._role_record_with_permissions(row) if row else None

    async def upsert_role(
        self,
        *,
        role_id: str,
        name: str,
        description: str | None = None,
        permissions: list[str] | None = None,
        built_in: bool = False,
    ) -> dict[str, Any]:
        await asyncio.to_thread(self._upsert_role_sync, role_id, name, description, permissions or [], bool(built_in))
        record = await self.get_role(role_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise role.")
        return record

    async def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict[str, Any] | None:
        updated = await asyncio.to_thread(self._set_role_permissions_sync, role_id, permissions)
        if not updated:
            return None
        return await self.get_role(role_id)

    async def list_user_roles(self, user_id: str) -> list[str]:
        rows = await self._fetchall(
            """
            SELECT role_id
            FROM enterprise_user_roles
            WHERE user_id = %s
            ORDER BY role_id ASC
            """,
            (user_id,),
        )
        return [str(row["role_id"]) for row in rows]

    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> list[str]:
        normalized = _normalized_strings(role_ids)
        await asyncio.to_thread(self._set_user_roles_sync, user_id, normalized)
        return normalized

    async def list_role_users(self, role_id: str) -> list[str]:
        rows = await self._fetchall(
            """
            SELECT user_id
            FROM enterprise_user_roles
            WHERE role_id = %s
            ORDER BY user_id ASC
            """,
            (role_id,),
        )
        return [str(row["user_id"]) for row in rows]

    async def delete_role(self, role_id: str) -> bool:
        return await asyncio.to_thread(self._delete_role_sync, role_id)

    async def _role_record_with_permissions(self, row: dict[str, Any]) -> dict[str, Any]:
        permissions = await self._fetchall(
            """
            SELECT permission
            FROM enterprise_role_permissions
            WHERE role_id = %s
            ORDER BY permission ASC
            """,
            (row["role_id"],),
        )
        return _role_record({**row, "permissions": [item["permission"] for item in permissions]})

    def _upsert_role_sync(
        self,
        role_id: str,
        name: str,
        description: str | None,
        permissions: list[str],
        built_in: bool,
    ) -> None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO enterprise_roles (role_id, name, description, built_in, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        description = VALUES(description),
                        built_in = VALUES(built_in),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (role_id, name, description, built_in),
                )
                _replace_role_permissions_sync(cursor, role_id, permissions)

    def _set_role_permissions_sync(self, role_id: str, permissions: list[str]) -> bool:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM enterprise_roles WHERE role_id = %s", (role_id,))
                if cursor.fetchone() is None:
                    return False
                _replace_role_permissions_sync(cursor, role_id, permissions)
                cursor.execute(
                    "UPDATE enterprise_roles SET updated_at = CURRENT_TIMESTAMP WHERE role_id = %s",
                    (role_id,),
                )
        return True

    def _set_user_roles_sync(self, user_id: str, role_ids: list[str]) -> None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                if role_ids:
                    placeholders = ", ".join(["%s"] * len(role_ids))
                    cursor.execute(
                        f"SELECT role_id FROM enterprise_roles WHERE role_id IN ({placeholders})",
                        tuple(role_ids),
                    )
                    existing = {str(row["role_id"]) for row in cursor.fetchall()}
                    missing = [role_id for role_id in role_ids if role_id not in existing]
                    if missing:
                        raise DatusException(
                            ErrorCode.COMMON_FIELD_INVALID,
                            message=f"Role not found: {missing[0]}.",
                        )
                cursor.execute("DELETE FROM enterprise_user_roles WHERE user_id = %s", (user_id,))
                if role_ids:
                    cursor.executemany(
                        """
                        INSERT INTO enterprise_user_roles (user_id, role_id, created_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        """,
                        [(user_id, role_id) for role_id in role_ids],
                    )

    def _delete_role_sync(self, role_id: str) -> bool:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT role_id FROM enterprise_roles WHERE role_id = %s FOR UPDATE", (role_id,))
                if cursor.fetchone() is None:
                    return False
                cursor.execute("SELECT 1 FROM enterprise_user_roles WHERE role_id = %s LIMIT 1", (role_id,))
                if cursor.fetchone() is not None:
                    return False
                cursor.execute("DELETE FROM enterprise_role_permissions WHERE role_id = %s", (role_id,))
                cursor.execute("DELETE FROM enterprise_roles WHERE role_id = %s", (role_id,))
                return int(cursor.rowcount or 0) > 0

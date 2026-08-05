"""PostgreSQL enterprise user and role metadata stores."""

from __future__ import annotations

from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.common.normalization import _like_contains_pattern, _normalized_strings
from datus_enterprise.storage.postgres.base import _PgStoreBase
from datus_enterprise.storage.postgres.records import (
    _affected_rows,
    _chat_preference_record,
    _replace_role_permissions,
    _role_record,
    _user_record,
)


class PgEnterpriseUserStore(_PgStoreBase):
    """PostgreSQL-backed enterprise user metadata store."""

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        if enabled is None:
            rows = await self._fetch(
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
                ORDER BY user_id ASC
                """
            )
        else:
            rows = await self._fetch(
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
                WHERE enabled = $1
                ORDER BY user_id ASC
                """,
                bool(enabled),
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
            params.append(bool(enabled))
            filters.append(f"u.enabled = ${len(params)}")
        if search and search.strip():
            params.append(_like_contains_pattern(search.strip()))
            placeholder = f"${len(params)}"
            filters.append(
                f"""(
                    u.user_id ILIKE {placeholder} ESCAPE '\\'
                    OR COALESCE(u.display_name, '') ILIKE {placeholder} ESCAPE '\\'
                    OR COALESCE(u.email, '') ILIKE {placeholder} ESCAPE '\\'
                    OR COALESCE(u.external_user_id, '') ILIKE {placeholder} ESCAPE '\\'
                    OR COALESCE(u.department, '') ILIKE {placeholder} ESCAPE '\\'
                    OR COALESCE(u.title, '') ILIKE {placeholder} ESCAPE '\\'
                    OR EXISTS (
                        SELECT 1 FROM enterprise_user_roles ur
                        WHERE ur.user_id = u.user_id AND ur.role_id ILIKE {placeholder} ESCAPE '\\'
                    )
                )"""
            )
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend((int(limit), int(offset)))
        rows = await self._fetch(
            f"""
            SELECT
                u.user_id,
                u.display_name,
                u.email,
                u.enabled,
                u.external_user_id,
                u.department,
                u.title,
                u.last_seen_at,
                u.created_at,
                u.updated_at
            FROM enterprise_users u
            {where_sql}
            ORDER BY u.user_id ASC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
        )
        return [_user_record(row) for row in rows]

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
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
            WHERE user_id = $1
            """,
            user_id,
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
        row = await self._fetchrow(
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
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), now())
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                email = excluded.email,
                enabled = excluded.enabled,
                external_user_id = excluded.external_user_id,
                department = excluded.department,
                title = excluded.title,
                last_seen_at = excluded.last_seen_at,
                updated_at = now()
            RETURNING
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
            """,
            user_id,
            display_name,
            email,
            bool(enabled),
            external_user_id,
            department,
            title,
            last_seen_at,
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise user.")
        return _user_record(row)

    async def set_user_enabled(self, user_id: str, enabled: bool) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            UPDATE enterprise_users
            SET enabled = $2, updated_at = now()
            WHERE user_id = $1
            RETURNING
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
            """,
            user_id,
            bool(enabled),
        )
        return _user_record(row) if row else None

    async def get_chat_preference(self, user_id: str) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            SELECT user_id, default_agent_id, created_at, updated_at
            FROM enterprise_user_chat_preferences
            WHERE user_id = $1
            """,
            user_id,
        )
        return _chat_preference_record(row, user_id=user_id)

    async def put_chat_preference(self, *, user_id: str, default_agent_id: str | None) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_user_chat_preferences (
                user_id, default_agent_id, created_at, updated_at
            )
            VALUES ($1, $2, now(), now())
            ON CONFLICT(user_id) DO UPDATE SET
                default_agent_id = excluded.default_agent_id,
                updated_at = now()
            RETURNING user_id, default_agent_id, created_at, updated_at
            """,
            user_id,
            default_agent_id,
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist user chat preference.")
        return _chat_preference_record(row, user_id=user_id)


class PgEnterpriseRoleStore(_PgStoreBase):
    """PostgreSQL-backed enterprise role metadata and membership store."""

    async def list_roles(self) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT
                role_id,
                name,
                description,
                built_in,
                created_at,
                updated_at,
                COALESCE(array_agg(permission ORDER BY permission)
                    FILTER (WHERE permission IS NOT NULL), ARRAY[]::text[]) AS permissions
            FROM enterprise_roles
            LEFT JOIN enterprise_role_permissions USING (role_id)
            GROUP BY role_id, name, description, built_in, created_at, updated_at
            ORDER BY role_id ASC
            """
        )
        return [_role_record(row) for row in rows]

    async def get_role(self, role_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT
                role_id,
                name,
                description,
                built_in,
                created_at,
                updated_at,
                COALESCE(array_agg(permission ORDER BY permission)
                    FILTER (WHERE permission IS NOT NULL), ARRAY[]::text[]) AS permissions
            FROM enterprise_roles
            LEFT JOIN enterprise_role_permissions USING (role_id)
            WHERE role_id = $1
            GROUP BY role_id, name, description, built_in, created_at, updated_at
            """,
            role_id,
        )
        return _role_record(row) if row else None

    async def upsert_role(
        self,
        *,
        role_id: str,
        name: str,
        description: str | None = None,
        permissions: list[str] | None = None,
        built_in: bool = False,
    ) -> dict[str, Any]:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO enterprise_roles (role_id, name, description, built_in, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, now(), now())
                    ON CONFLICT(role_id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        built_in = excluded.built_in,
                        updated_at = now()
                    """,
                    role_id,
                    name,
                    description,
                    bool(built_in),
                )
                await _replace_role_permissions(conn, role_id, permissions or [])
        record = await self.get_role(role_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise role.")
        return record

    async def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict[str, Any] | None:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchrow("SELECT 1 FROM enterprise_roles WHERE role_id = $1", role_id)
                if exists is None:
                    return None
                await _replace_role_permissions(conn, role_id, permissions)
                await conn.execute(
                    "UPDATE enterprise_roles SET updated_at = now() WHERE role_id = $1",
                    role_id,
                )
        return await self.get_role(role_id)

    async def list_user_roles(self, user_id: str) -> list[str]:
        rows = await self._fetch(
            """
            SELECT role_id
            FROM enterprise_user_roles
            WHERE user_id = $1
            ORDER BY role_id ASC
            """,
            user_id,
        )
        return [str(row["role_id"]) for row in rows]

    async def set_user_roles(self, user_id: str, role_ids: list[str]) -> list[str]:
        normalized = _normalized_strings(role_ids)
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                if normalized:
                    rows = await conn.fetch(
                        "SELECT role_id FROM enterprise_roles WHERE role_id = ANY($1::text[])",
                        normalized,
                    )
                    existing_role_ids = {str(row["role_id"]) for row in rows}
                    missing_role_ids = [role_id for role_id in normalized if role_id not in existing_role_ids]
                    if missing_role_ids:
                        raise DatusException(
                            ErrorCode.COMMON_FIELD_INVALID,
                            message=f"Role not found: {missing_role_ids[0]}.",
                        )
                await conn.execute("DELETE FROM enterprise_user_roles WHERE user_id = $1", user_id)
                if normalized:
                    await conn.executemany(
                        """
                        INSERT INTO enterprise_user_roles (user_id, role_id, created_at)
                        VALUES ($1, $2, now())
                        """,
                        [(user_id, role_id) for role_id in normalized],
                    )
        return normalized

    async def list_role_users(self, role_id: str) -> list[str]:
        rows = await self._fetch(
            """
            SELECT user_id
            FROM enterprise_user_roles
            WHERE role_id = $1
            ORDER BY user_id ASC
            """,
            role_id,
        )
        return [str(row["user_id"]) for row in rows]

    async def delete_role(self, role_id: str) -> bool:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                role = await conn.fetchrow(
                    "SELECT role_id FROM enterprise_roles WHERE role_id = $1 FOR UPDATE",
                    role_id,
                )
                if role is None:
                    return False
                assigned = await conn.fetchrow(
                    "SELECT 1 FROM enterprise_user_roles WHERE role_id = $1 LIMIT 1",
                    role_id,
                )
                if assigned:
                    return False
                result = await conn.execute("DELETE FROM enterprise_roles WHERE role_id = $1", role_id)
        return _affected_rows(result) > 0

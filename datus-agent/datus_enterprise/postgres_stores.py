"""PostgreSQL-backed enterprise metadata stores.

The current schema bootstrap is intentionally limited to `_SCHEMA_SQL` with
`CREATE TABLE IF NOT EXISTS`. Production migration tooling, versioning, and
rollback workflows are a later enterprise operations slice.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime, timezone
from typing import Any

from datus.api.enterprise.models import AuditEvent
from datus.utils.exceptions import DatusException, ErrorCode


class _PgStoreBase:
    """Lazy asyncpg pool owner with idempotent schema initialization."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 2,
        command_timeout: float | None = 30.0,
    ) -> None:
        if not str(dsn or "").strip():
            raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="PostgreSQL DSN is required.")
        self._dsn = dsn
        self._min_size = int(min_size)
        self._max_size = int(max_size)
        self._command_timeout = command_timeout
        self._pool: Any | None = None
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute(_SCHEMA_SQL)
            self._schema_ready = True

    async def _get_pool(self) -> Any:
        if self._pool is None:
            asyncpg = importlib.import_module("asyncpg")
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=self._command_timeout,
            )
        return self._pool

    async def close(self) -> None:
        """Close the owned asyncpg pool."""
        pool = self._pool
        if pool is None:
            return
        await pool.close()
        self._pool = None
        self._schema_ready = False

    async def _fetch(self, query: str, *args: Any) -> list[Any]:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return list(await conn.fetch(query, *args))

    async def _fetchrow(self, query: str, *args: Any) -> Any | None:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def _execute(self, query: str, *args: Any) -> str:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return str(await conn.execute(query, *args))


class PgEnterpriseUserStore(_PgStoreBase):
    """PostgreSQL-backed enterprise user metadata store."""

    async def list_users(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        if enabled is None:
            rows = await self._fetch(
                """
                SELECT user_id, display_name, email, enabled, created_at, updated_at
                FROM enterprise_users
                ORDER BY user_id ASC
                """
            )
        else:
            rows = await self._fetch(
                """
                SELECT user_id, display_name, email, enabled, created_at, updated_at
                FROM enterprise_users
                WHERE enabled = $1
                ORDER BY user_id ASC
                """,
                bool(enabled),
            )
        return [_user_record(row) for row in rows]

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT user_id, display_name, email, enabled, created_at, updated_at
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
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_users (user_id, display_name, email, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, now(), now())
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                email = excluded.email,
                enabled = excluded.enabled,
                updated_at = now()
            RETURNING user_id, display_name, email, enabled, created_at, updated_at
            """,
            user_id,
            display_name,
            email,
            bool(enabled),
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
            RETURNING user_id, display_name, email, enabled, created_at, updated_at
            """,
            user_id,
            bool(enabled),
        )
        return _user_record(row) if row else None


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


class PgEnterpriseDatasourceGrantStore(_PgStoreBase):
    """PostgreSQL-backed datasource grant metadata store."""

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
        }
        where_sql, params = _where(filters)
        rows = await self._fetch(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """,
            *params,
        )
        return [_datasource_grant_record(row) for row in rows]

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            WHERE subject_type = $1 AND subject_id = $2 AND datasource_key = $3
            """,
            subject_type,
            subject_id,
            datasource_key,
        )
        return _datasource_grant_record(row) if row else None

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
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_datasource_grants (
                subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, now(), now())
            ON CONFLICT(subject_type, subject_id, datasource_key) DO UPDATE SET
                effect = excluded.effect,
                scope_json = excluded.scope_json,
                updated_at = now()
            RETURNING subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            """,
            subject_type,
            subject_id,
            datasource_key,
            normalized_effect,
            json.dumps(normalized_scope, sort_keys=True, separators=(",", ":")),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist datasource grant.")
        return _datasource_grant_record(row)

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        result = await self._execute(
            """
            DELETE FROM enterprise_datasource_grants
            WHERE subject_type = $1 AND subject_id = $2 AND datasource_key = $3
            """,
            subject_type,
            subject_id,
            datasource_key,
        )
        return _affected_rows(result) > 0


class PgEnterpriseAgentStore(_PgStoreBase):
    """PostgreSQL-backed enterprise custom agent metadata store."""

    async def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = await self._fetch(
                """
                SELECT
                    agent_id,
                    name,
                    description,
                    node_class,
                    status,
                    owner_user_id,
                    datasource_id,
                    artifact_slug,
                    prompt_template,
                    prompt_language,
                    prompt_version,
                    tools,
                    mcp,
                    skills,
                    scoped_context_json,
                    rules,
                    max_turns,
                    acl_json,
                    created_at,
                    updated_at
                FROM enterprise_agents
                ORDER BY agent_id ASC
                """
            )
        else:
            normalized_status = _normalized_agent_status(status)
            rows = await self._fetch(
                """
                SELECT
                    agent_id,
                    name,
                    description,
                    node_class,
                    status,
                    owner_user_id,
                    datasource_id,
                    artifact_slug,
                    prompt_template,
                    prompt_language,
                    prompt_version,
                    tools,
                    mcp,
                    skills,
                    scoped_context_json,
                    rules,
                    max_turns,
                    acl_json,
                    created_at,
                    updated_at
                FROM enterprise_agents
                WHERE status = $1
                ORDER BY agent_id ASC
                """,
                normalized_status,
            )
        return [_agent_record(row) for row in rows]

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT
                agent_id,
                name,
                description,
                node_class,
                status,
                owner_user_id,
                datasource_id,
                artifact_slug,
                prompt_template,
                prompt_language,
                prompt_version,
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            FROM enterprise_agents
            WHERE agent_id = $1
            """,
            agent_id,
        )
        return _agent_record(row) if row else None

    async def put_agent(self, *, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalized_agent_metadata({"agent_id": agent_id, **dict(payload)})
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_agents (
                agent_id,
                name,
                description,
                node_class,
                status,
                owner_user_id,
                datasource_id,
                artifact_slug,
                prompt_template,
                prompt_language,
                prompt_version,
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12::text[],
                $13::text[],
                $14::text[],
                $15::jsonb,
                $16::text[],
                $17,
                $18::jsonb,
                now(),
                now()
            )
            ON CONFLICT(agent_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                node_class = excluded.node_class,
                status = excluded.status,
                owner_user_id = excluded.owner_user_id,
                datasource_id = excluded.datasource_id,
                artifact_slug = excluded.artifact_slug,
                prompt_template = excluded.prompt_template,
                prompt_language = excluded.prompt_language,
                prompt_version = excluded.prompt_version,
                tools = excluded.tools,
                mcp = excluded.mcp,
                skills = excluded.skills,
                scoped_context_json = excluded.scoped_context_json,
                rules = excluded.rules,
                max_turns = excluded.max_turns,
                acl_json = excluded.acl_json,
                updated_at = now()
            RETURNING
                agent_id,
                name,
                description,
                node_class,
                status,
                owner_user_id,
                datasource_id,
                artifact_slug,
                prompt_template,
                prompt_language,
                prompt_version,
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
            normalized["agent_id"],
            normalized["name"],
            normalized["description"],
            normalized["node_class"],
            normalized["status"],
            normalized["owner_user_id"],
            normalized["datasource_id"],
            normalized["artifact_slug"],
            normalized["prompt_template"],
            normalized["prompt_language"],
            normalized["prompt_version"],
            normalized["tools"],
            normalized["mcp"],
            normalized["skills"],
            json.dumps(normalized["scoped_context"], ensure_ascii=False, sort_keys=True),
            normalized["rules"],
            normalized["max_turns"],
            json.dumps(normalized["acl"], ensure_ascii=False, sort_keys=True),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise agent.")
        return _agent_record(row)

    async def set_agent_status(self, agent_id: str, status: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            UPDATE enterprise_agents
            SET status = $2, updated_at = now()
            WHERE agent_id = $1
            RETURNING
                agent_id,
                name,
                description,
                node_class,
                status,
                owner_user_id,
                datasource_id,
                artifact_slug,
                prompt_template,
                prompt_language,
                prompt_version,
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
            agent_id,
            _normalized_agent_status(status),
        )
        return _agent_record(row) if row else None

    async def put_agent_acl(self, agent_id: str, acl: dict[str, Any]) -> dict[str, Any] | None:
        normalized_acl = _normalized_agent_acl(acl)
        row = await self._fetchrow(
            """
            UPDATE enterprise_agents
            SET acl_json = $2::jsonb, updated_at = now()
            WHERE agent_id = $1
            RETURNING
                agent_id,
                name,
                description,
                node_class,
                status,
                owner_user_id,
                datasource_id,
                artifact_slug,
                prompt_template,
                prompt_language,
                prompt_version,
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
            agent_id,
            json.dumps(normalized_acl, ensure_ascii=False, sort_keys=True),
        )
        return _agent_record(row) if row else None

    async def delete_agent(self, agent_id: str) -> bool:
        result = await self._execute("DELETE FROM enterprise_agents WHERE agent_id = $1", agent_id)
        return _affected_rows(result) > 0


class PgSessionOwnerStore(_PgStoreBase):
    """PostgreSQL-backed session owner metadata store."""

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        await self._execute(
            """
            INSERT INTO session_owners (project_id, session_id, user_id, created_at, updated_at)
            VALUES ($1, $2, $3, now(), now())
            ON CONFLICT(project_id, session_id) DO UPDATE SET
                user_id = excluded.user_id,
                updated_at = now()
            """,
            project_id,
            session_id,
            user_id,
        )

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        row = await self._fetchrow(
            """
            SELECT user_id
            FROM session_owners
            WHERE project_id = $1 AND session_id = $2
            """,
            project_id,
            session_id,
        )
        return str(row["user_id"]) if row else None

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        await self._execute(
            "DELETE FROM session_owners WHERE project_id = $1 AND session_id = $2",
            project_id,
            session_id,
        )

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        rows = await self._fetch(
            """
            SELECT session_id
            FROM session_owners
            WHERE project_id = $1 AND user_id = $2
            ORDER BY updated_at DESC, session_id ASC
            """,
            project_id,
            user_id,
        )
        return [str(row["session_id"]) for row in rows]

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        if user_id is None:
            rows = await self._fetch(
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = $1
                ORDER BY updated_at DESC, session_id ASC
                """,
                project_id,
            )
        else:
            rows = await self._fetch(
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = $1 AND user_id = $2
                ORDER BY updated_at DESC, session_id ASC
                """,
                project_id,
                user_id,
            )
        return [_session_owner_record(row) for row in rows]


class PgArtifactAclStore(_PgStoreBase):
    """PostgreSQL-backed artifact ACL metadata store."""

    async def get_acl(self, *, artifact_type: str, slug: str) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            SELECT acl_json
            FROM enterprise_artifact_acls
            WHERE artifact_type = $1 AND slug = $2
            """,
            artifact_type,
            slug,
        )
        if row is None:
            raise KeyError((artifact_type, slug))
        return _artifact_acl_record(row)

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict[str, Any]) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_artifact_acls (artifact_type, slug, acl_json, created_at, updated_at)
            VALUES ($1, $2, $3::jsonb, now(), now())
            ON CONFLICT(artifact_type, slug) DO UPDATE SET
                acl_json = excluded.acl_json,
                updated_at = now()
            RETURNING acl_json
            """,
            artifact_type,
            slug,
            json.dumps(acl, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist artifact ACL.")
        return _artifact_acl_record(row)


class PgAuditSink(_PgStoreBase):
    """PostgreSQL-backed audit sink and query reader."""

    async def write(self, event: AuditEvent) -> None:
        await self._execute(
            """
            INSERT INTO enterprise_audit_logs (
                user_id,
                action,
                resource_type,
                resource_id,
                decision,
                reason,
                request_id,
                metadata_json,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, now())
            """,
            event.user_id,
            event.action,
            event.resource_type,
            event.resource_id,
            event.decision,
            event.reason,
            event.request_id,
            json.dumps(event.metadata, ensure_ascii=False, sort_keys=True, default=str),
        )

    async def query_events(
        self,
        *,
        limit: int,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        decision: str | None = None,
    ) -> list[AuditEvent]:
        filters = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "decision": decision,
        }
        where_sql, params = _where(filters)
        params.append(max(1, int(limit)))
        rows = await self._fetch(
            f"""
            SELECT user_id, action, resource_type, resource_id, decision, reason, request_id, metadata_json
            FROM enterprise_audit_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT ${len(params)}
            """,
            *params,
        )
        return [_audit_event(row) for row in rows]


class PgEnterpriseQuotaStore(_PgStoreBase):
    """PostgreSQL-backed enterprise quota metadata and usage store."""

    async def list_quotas(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where({"subject_type": subject_type, "subject_id": subject_id, "resource": resource})
        rows = await self._fetch(
            f"""
            SELECT subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
            FROM enterprise_quotas
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, resource ASC
            """,
            *params,
        )
        return [_quota_record(row) for row in rows]

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
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_quotas (
                subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, now(), now())
            ON CONFLICT(subject_type, subject_id, resource) DO UPDATE SET
                limit_value = excluded.limit_value,
                window_seconds = excluded.window_seconds,
                enabled = excluded.enabled,
                updated_at = now()
            RETURNING subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
            """,
            subject_type,
            subject_id,
            resource,
            int(limit),
            int(window_seconds),
            bool(enabled),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise quota.")
        return _quota_record(row)

    async def list_usage(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where({"subject_type": subject_type, "subject_id": subject_id, "resource": resource})
        rows = await self._fetch(
            f"""
            SELECT subject_type, subject_id, resource, window_start, used, updated_at
            FROM enterprise_quota_usage
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, resource ASC, window_start DESC
            """,
            *params,
        )
        return [_quota_usage_record(row) for row in rows]

    async def consume_quota(
        self,
        *,
        subjects: list[dict[str, str]],
        resource: str,
        amount: int = 1,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Quota consume amount must be positive.")
        normalized_subjects = _normalized_quota_subjects(subjects)
        if not normalized_subjects:
            return {"allowed": True, "usage": []}

        subject_types = [subject["subject_type"] for subject in normalized_subjects]
        subject_ids = [subject["subject_id"] for subject in normalized_subjects]
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                quota_rows = await conn.fetch(
                    """
                    SELECT subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
                    FROM enterprise_quotas
                    WHERE resource = $1
                        AND enabled = true
                        AND (subject_type, subject_id) IN (
                            SELECT subject_type, subject_id
                            FROM unnest($2::text[], $3::text[]) AS subject(subject_type, subject_id)
                        )
                    ORDER BY subject_type ASC, subject_id ASC
                    FOR UPDATE
                    """,
                    resource,
                    subject_types,
                    subject_ids,
                )

                applicable: list[tuple[Any, dict[str, Any]]] = []
                for quota in quota_rows:
                    usage = await self._current_usage_for_quota(conn, quota, now)
                    if int(usage["used"]) + amount > int(quota["limit_value"]):
                        return {
                            "allowed": False,
                            "reason": "quota exceeded",
                            "subject_type": str(quota["subject_type"]),
                            "subject_id": str(quota["subject_id"]),
                            "resource": str(quota["resource"]),
                            "limit": int(quota["limit_value"]),
                            "used": int(usage["used"]),
                            "remaining": max(int(quota["limit_value"]) - int(usage["used"]), 0),
                            "window_start": _iso(usage["window_start"]),
                            "window_seconds": int(quota["window_seconds"]),
                        }
                    applicable.append((quota, usage))

                updated_usage = []
                for quota, usage in applicable:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO enterprise_quota_usage (
                            subject_type, subject_id, resource, window_start, used, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, now())
                        ON CONFLICT(subject_type, subject_id, resource, window_start) DO UPDATE SET
                            used = enterprise_quota_usage.used + $5,
                            updated_at = now()
                        RETURNING subject_type, subject_id, resource, window_start, used, updated_at
                        """,
                        quota["subject_type"],
                        quota["subject_id"],
                        quota["resource"],
                        usage["window_start"],
                        amount,
                    )
                    if row is not None:
                        record = _quota_usage_record(row)
                        record["window_seconds"] = int(quota["window_seconds"])
                        updated_usage.append(record)

        return {"allowed": True, "usage": updated_usage}

    async def _current_usage_for_quota(self, conn: Any, quota: Any, now: datetime) -> dict[str, Any]:
        window_floor = now.timestamp() - int(quota["window_seconds"])
        row = await conn.fetchrow(
            """
            SELECT subject_type, subject_id, resource, window_start, used, updated_at
            FROM enterprise_quota_usage
            WHERE subject_type = $1
                AND subject_id = $2
                AND resource = $3
                AND window_start > to_timestamp($4)
            ORDER BY window_start DESC
            LIMIT 1
            FOR UPDATE
            """,
            quota["subject_type"],
            quota["subject_id"],
            quota["resource"],
            window_floor,
        )
        if row is not None:
            return dict(row)
        return {
            "subject_type": quota["subject_type"],
            "subject_id": quota["subject_id"],
            "resource": quota["resource"],
            "window_start": now,
            "used": 0,
            "updated_at": now,
        }


class PgEnterpriseSecretStore(_PgStoreBase):
    """PostgreSQL-backed secret reference store.

    Only secret references are stored here. Secret values remain in the external
    provider named by each record.
    """

    async def list_secrets(self, *, prefix: str | None = None) -> list[dict[str, Any]]:
        if prefix is None:
            rows = await self._fetch(
                """
                SELECT name, provider, reference, description, enabled, created_at, updated_at
                FROM enterprise_secrets
                ORDER BY name ASC
                """
            )
        else:
            rows = await self._fetch(
                """
                SELECT name, provider, reference, description, enabled, created_at, updated_at
                FROM enterprise_secrets
                WHERE name LIKE $1 ESCAPE '\\'
                ORDER BY name ASC
                """,
                _like_prefix_pattern(prefix),
            )
        return [_secret_record(row) for row in rows]

    async def get_secret(self, name: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT name, provider, reference, description, enabled, created_at, updated_at
            FROM enterprise_secrets
            WHERE name = $1
            """,
            name,
        )
        return _secret_record(row) if row else None

    async def put_secret(
        self,
        *,
        name: str,
        provider: str,
        reference: str,
        description: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_secrets (name, provider, reference, description, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, now(), now())
            ON CONFLICT(name) DO UPDATE SET
                provider = excluded.provider,
                reference = excluded.reference,
                description = excluded.description,
                enabled = excluded.enabled,
                updated_at = now()
            RETURNING name, provider, reference, description, enabled, created_at, updated_at
            """,
            name,
            provider,
            reference,
            description,
            bool(enabled),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise secret.")
        return _secret_record(row)

    async def delete_secret(self, name: str) -> bool:
        result = await self._execute("DELETE FROM enterprise_secrets WHERE name = $1", name)
        return _affected_rows(result) > 0


async def _replace_role_permissions(conn: Any, role_id: str, permissions: list[str]) -> None:
    await conn.execute("DELETE FROM enterprise_role_permissions WHERE role_id = $1", role_id)
    normalized = _normalized_strings(permissions)
    if normalized:
        await conn.executemany(
            """
            INSERT INTO enterprise_role_permissions (role_id, permission)
            VALUES ($1, $2)
            """,
            [(role_id, permission) for permission in normalized],
        )


def _where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses = []
    params = []
    for column, value in filters.items():
        if value is None:
            continue
        params.append(value)
        clauses.append(f"{column} = ${len(params)}")
    if not clauses:
        return "", params
    return f"WHERE {' AND '.join(clauses)}", params


def _normalized_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _normalized_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = values.split(",")
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        return []
    return sorted({str(value).strip() for value in raw_values if str(value).strip()})


def _normalized_agent_status(status: Any) -> str:
    normalized = str(status or "draft").strip().lower()
    if normalized not in {"draft", "published", "disabled", "archived"}:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message="Enterprise agent status must be one of: archived, disabled, draft, published.",
        )
    return normalized


def _normalized_agent_acl(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    visibility = str(raw.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "role", "enterprise"}:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message="Enterprise agent visibility must be one of: enterprise, private, role.",
        )
    return {
        "visibility": visibility,
        "allowed_roles": _normalized_string_list(raw.get("allowed_roles")),
        "allowed_user_ids": _normalized_string_list(raw.get("allowed_user_ids")),
    }


def _normalized_agent_metadata(record: dict[str, Any]) -> dict[str, Any]:
    agent_id = str(record.get("agent_id") or "").strip()
    if not agent_id:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Enterprise agent id is required.")
    scoped_context = record.get("scoped_context")
    if scoped_context is not None and not isinstance(scoped_context, dict):
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID, message="Enterprise agent scoped_context must be a mapping."
        )
    return {
        "agent_id": agent_id,
        "name": str(record.get("name") or agent_id).strip(),
        "description": _optional_str(record.get("description")),
        "node_class": str(record.get("node_class") or record.get("type") or "gen_sql").strip(),
        "status": _normalized_agent_status(record.get("status")),
        "owner_user_id": _optional_str(record.get("owner_user_id")),
        "datasource_id": _optional_str(record.get("datasource_id")),
        "artifact_slug": _optional_str(record.get("artifact_slug")),
        "prompt_template": _optional_str(record.get("prompt_template")),
        "prompt_language": str(record.get("prompt_language") or "en").strip(),
        "prompt_version": _optional_str(record.get("prompt_version")) or "1.0",
        "tools": _normalized_string_list(record.get("tools")),
        "mcp": _normalized_string_list(record.get("mcp")),
        "skills": _normalized_string_list(record.get("skills")),
        "scoped_context": dict(scoped_context or {}),
        "rules": _normalized_string_list(record.get("rules")),
        "max_turns": int(record.get("max_turns") or 30),
        "acl": _normalized_agent_acl(record.get("acl")),
    }


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


def _load_jsonb(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _like_prefix_pattern(prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def _normalized_quota_subjects(subjects: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    seen: set[tuple[str, str]] = set()
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        subject_type = str(subject.get("subject_type") or "").strip()
        subject_id = str(subject.get("subject_id") or "").strip()
        if subject_type not in {"global", "role", "user"} or not subject_id:
            continue
        key = (subject_type, subject_id)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"subject_type": subject_type, "subject_id": subject_id})
    return normalized


def _user_record(row: Any) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "display_name": _optional_str(row["display_name"]),
        "email": _optional_str(row["email"]),
        "enabled": bool(row["enabled"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _role_record(row: Any) -> dict[str, Any]:
    return {
        "role_id": str(row["role_id"]),
        "name": str(row["name"]),
        "description": _optional_str(row["description"]),
        "permissions": _normalized_strings(list(row["permissions"] or [])),
        "built_in": bool(row["built_in"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _datasource_grant_record(row: Any) -> dict[str, Any]:
    return {
        "subject_type": str(row["subject_type"]),
        "subject_id": str(row["subject_id"]),
        "datasource_key": str(row["datasource_key"]),
        "effect": _normalized_grant_effect(row["effect"]),
        "scope": _normalized_grant_scope(_load_jsonb(row["scope_json"])),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _agent_record(row: Any) -> dict[str, Any]:
    return {
        "agent_id": str(row["agent_id"]),
        "name": str(row["name"]),
        "description": _optional_str(row["description"]),
        "node_class": str(row["node_class"]),
        "status": _normalized_agent_status(row["status"]),
        "owner_user_id": _optional_str(row["owner_user_id"]),
        "datasource_id": _optional_str(row["datasource_id"]),
        "artifact_slug": _optional_str(row["artifact_slug"]),
        "prompt_template": _optional_str(row["prompt_template"]),
        "prompt_language": str(row["prompt_language"] or "en"),
        "prompt_version": _optional_str(row["prompt_version"]) or "1.0",
        "tools": _normalized_strings(list(row["tools"] or [])),
        "mcp": _normalized_strings(list(row["mcp"] or [])),
        "skills": _normalized_strings(list(row["skills"] or [])),
        "scoped_context": _load_jsonb(row["scoped_context_json"]),
        "rules": _normalized_strings(list(row["rules"] or [])),
        "max_turns": int(row["max_turns"] or 30),
        "acl": _normalized_agent_acl(_load_jsonb(row["acl_json"])),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _session_owner_record(row: Any) -> dict[str, Any]:
    return {
        "project_id": str(row["project_id"]),
        "session_id": str(row["session_id"]),
        "user_id": str(row["user_id"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _audit_event(row: Any) -> AuditEvent:
    return AuditEvent(
        user_id=_optional_str(row["user_id"]),
        action=str(row["action"]),
        resource_type=str(row["resource_type"]),
        resource_id=_optional_str(row["resource_id"]),
        decision=str(row["decision"]),
        reason=_optional_str(row["reason"]),
        request_id=_optional_str(row["request_id"]),
        metadata=_load_jsonb(row["metadata_json"]),
    )


def _artifact_acl_record(row: Any) -> dict[str, Any]:
    return _load_jsonb(row["acl_json"])


def _quota_record(row: Any) -> dict[str, Any]:
    return {
        "subject_type": str(row["subject_type"]),
        "subject_id": str(row["subject_id"]),
        "resource": str(row["resource"]),
        "limit": int(row["limit_value"]),
        "window_seconds": int(row["window_seconds"]),
        "enabled": bool(row["enabled"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _quota_usage_record(row: Any) -> dict[str, Any]:
    return {
        "subject_type": str(row["subject_type"]),
        "subject_id": str(row["subject_id"]),
        "resource": str(row["resource"]),
        "used": int(row["used"]),
        "window_start": _iso(row["window_start"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _secret_record(row: Any) -> dict[str, Any]:
    return {
        "name": str(row["name"]),
        "provider": str(row["provider"]),
        "reference": str(row["reference"]),
        "description": _optional_str(row["description"]),
        "enabled": bool(row["enabled"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return str(value) or None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _affected_rows(result: Any) -> int:
    parts = str(result or "").split()
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_users (
    user_id text PRIMARY KEY,
    display_name text,
    email text,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_users_enabled
ON enterprise_users (enabled, user_id);

CREATE TABLE IF NOT EXISTS enterprise_roles (
    role_id text PRIMARY KEY,
    name text NOT NULL,
    description text,
    built_in boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_role_permissions (
    role_id text NOT NULL REFERENCES enterprise_roles(role_id) ON DELETE CASCADE,
    permission text NOT NULL,
    PRIMARY KEY (role_id, permission)
);

CREATE TABLE IF NOT EXISTS enterprise_user_roles (
    user_id text NOT NULL,
    role_id text NOT NULL REFERENCES enterprise_roles(role_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_user_roles_role
ON enterprise_user_roles (role_id, user_id);

CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    datasource_key text NOT NULL,
    effect text NOT NULL,
    scope_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, datasource_key)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_datasource_grants_datasource
ON enterprise_datasource_grants (datasource_key, subject_type, subject_id);

CREATE TABLE IF NOT EXISTS enterprise_agents (
    agent_id text PRIMARY KEY,
    name text NOT NULL,
    description text,
    node_class text NOT NULL,
    status text NOT NULL,
    owner_user_id text,
    datasource_id text,
    artifact_slug text,
    prompt_template text,
    prompt_language text NOT NULL DEFAULT 'en',
    prompt_version text NOT NULL DEFAULT '1.0',
    tools text[] NOT NULL DEFAULT ARRAY[]::text[],
    mcp text[] NOT NULL DEFAULT ARRAY[]::text[],
    skills text[] NOT NULL DEFAULT ARRAY[]::text[],
    scoped_context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    rules text[] NOT NULL DEFAULT ARRAY[]::text[],
    max_turns integer NOT NULL DEFAULT 30,
    acl_json jsonb NOT NULL DEFAULT '{"visibility":"private","allowed_roles":[],"allowed_user_ids":[]}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_agents_status
ON enterprise_agents (status, agent_id);

CREATE INDEX IF NOT EXISTS idx_enterprise_agents_owner
ON enterprise_agents (owner_user_id, agent_id);

CREATE TABLE IF NOT EXISTS session_owners (
    project_id text NOT NULL,
    session_id text NOT NULL,
    user_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_session_owners_user
ON session_owners (project_id, user_id, updated_at);

CREATE TABLE IF NOT EXISTS enterprise_artifact_acls (
    artifact_type text NOT NULL,
    slug text NOT NULL,
    acl_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (artifact_type, slug)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_artifact_acls_type_updated
ON enterprise_artifact_acls (artifact_type, updated_at);

CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
    id bigserial PRIMARY KEY,
    user_id text,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    decision text NOT NULL,
    reason text,
    request_id text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_created_at
ON enterprise_audit_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_user_id
ON enterprise_audit_logs (user_id);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_action
ON enterprise_audit_logs (action);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_resource_type
ON enterprise_audit_logs (resource_type);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_decision
ON enterprise_audit_logs (decision);

CREATE TABLE IF NOT EXISTS enterprise_quotas (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    resource text NOT NULL,
    limit_value integer NOT NULL,
    window_seconds integer NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, resource)
);

CREATE TABLE IF NOT EXISTS enterprise_quota_usage (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    resource text NOT NULL,
    window_start timestamptz NOT NULL,
    used integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, resource, window_start)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_quota_usage_filter
ON enterprise_quota_usage (subject_type, subject_id, resource, window_start DESC);

CREATE TABLE IF NOT EXISTS enterprise_secrets (
    name text PRIMARY KEY,
    provider text NOT NULL,
    reference text NOT NULL,
    description text,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

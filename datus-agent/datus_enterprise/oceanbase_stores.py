"""OceanBase MySQL-backed enterprise metadata stores.

The current schema bootstrap is intentionally limited to ``CREATE DATABASE IF
NOT EXISTS`` / ``CREATE TABLE IF NOT EXISTS`` statements. Production migration
tooling, versioning, and rollback workflows are a separate operations slice.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from datus.api.enterprise.models import AuditEvent
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.time_utils import to_utc_iso
from datus_enterprise.model_credentials import CredentialSecretCodec, api_key_hint
from datus_enterprise.oceanbase_common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
)
from datus_enterprise.personal_datasources import password_hint


class _ObStoreBase(OceanBaseSchemaMixin):
    """Blocking PyMySQL store base exposed through async protocol methods."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
    ) -> None:
        self._config = OceanBaseMySQLConfig.from_kwargs(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        self._pool = OceanBaseMySQLPool(self._config)
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    async def close(self) -> None:
        await asyncio.to_thread(self._pool.close)

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        return await asyncio.to_thread(self._execute_sync, query, params)

    async def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._fetchone_sync, query, params)

    async def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetchall_sync, query, params)

    def _execute_sync(self, query: str, params: tuple[Any, ...] = ()) -> int:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return int(cursor.rowcount or 0)

    def _fetchone_sync(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None

    def _fetchall_sync(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]


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


class ObEnterpriseDatasourceGrantStore(_ObStoreBase):
    """OceanBase MySQL-backed datasource grant metadata store."""

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where_mysql(
            {"subject_type": subject_type, "subject_id": subject_id, "datasource_key": datasource_key}
        )
        rows = await self._fetchall(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """,
            tuple(params),
        )
        return [_datasource_grant_record(row) for row in rows]

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            WHERE subject_type = %s AND subject_id = %s AND datasource_key = %s
            """,
            (subject_type, subject_id, datasource_key),
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
        await self._execute(
            """
            INSERT INTO enterprise_datasource_grants (
                subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                effect = VALUES(effect),
                scope_json = VALUES(scope_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                subject_type,
                subject_id,
                datasource_key,
                normalized_effect,
                json.dumps(normalized_scope, sort_keys=True, separators=(",", ":")),
            ),
        )
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
        count = await self._execute(
            """
            DELETE FROM enterprise_datasource_grants
            WHERE subject_type = %s AND subject_id = %s AND datasource_key = %s
            """,
            (subject_type, subject_id, datasource_key),
        )
        return count > 0


class ObEnterpriseAgentStore(_ObStoreBase):
    """OceanBase MySQL-backed enterprise custom agent metadata store."""

    async def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = await self._fetchall(f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents ORDER BY agent_id ASC")
        else:
            rows = await self._fetchall(
                f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents WHERE status = %s ORDER BY agent_id ASC",
                (_normalized_agent_status(status),),
            )
        return [_agent_record(row) for row in rows]

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents WHERE agent_id = %s",
            (agent_id,),
        )
        return _agent_record(row) if row else None

    async def put_agent(self, *, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalized_agent_metadata({"agent_id": agent_id, **dict(payload)})
        await self._execute(
            """
            INSERT INTO enterprise_agents (
                agent_id, name, description, node_class, status, owner_user_id, datasource_id, artifact_slug,
                prompt_template, prompt_language, prompt_version, tools_json, mcp_json, skills_json,
                scoped_context_json, rules_json, max_turns, acl_json, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                description = VALUES(description),
                node_class = VALUES(node_class),
                status = VALUES(status),
                owner_user_id = VALUES(owner_user_id),
                datasource_id = VALUES(datasource_id),
                artifact_slug = VALUES(artifact_slug),
                prompt_template = VALUES(prompt_template),
                prompt_language = VALUES(prompt_language),
                prompt_version = VALUES(prompt_version),
                tools_json = VALUES(tools_json),
                mcp_json = VALUES(mcp_json),
                skills_json = VALUES(skills_json),
                scoped_context_json = VALUES(scoped_context_json),
                rules_json = VALUES(rules_json),
                max_turns = VALUES(max_turns),
                acl_json = VALUES(acl_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
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
                json.dumps(normalized["tools"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["mcp"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["skills"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["scoped_context"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["rules"], ensure_ascii=False, sort_keys=True),
                normalized["max_turns"],
                json.dumps(normalized["acl"], ensure_ascii=False, sort_keys=True),
            ),
        )
        record = await self.get_agent(normalized["agent_id"])
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise agent.")
        return record

    async def set_agent_status(self, agent_id: str, status: str) -> dict[str, Any] | None:
        await self._execute(
            "UPDATE enterprise_agents SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE agent_id = %s",
            (_normalized_agent_status(status), agent_id),
        )
        return await self.get_agent(agent_id)

    async def put_agent_acl(self, agent_id: str, acl: dict[str, Any]) -> dict[str, Any] | None:
        await self._execute(
            "UPDATE enterprise_agents SET acl_json = %s, updated_at = CURRENT_TIMESTAMP WHERE agent_id = %s",
            (json.dumps(_normalized_agent_acl(acl), ensure_ascii=False, sort_keys=True), agent_id),
        )
        return await self.get_agent(agent_id)

    async def delete_agent(self, agent_id: str) -> bool:
        return await self._execute("DELETE FROM enterprise_agents WHERE agent_id = %s", (agent_id,)) > 0


class ObSessionOwnerStore(_ObStoreBase):
    """OceanBase MySQL-backed session owner metadata store."""

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        await self._execute(
            """
            INSERT INTO session_owners (project_id, session_id, user_id, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
              user_id = VALUES(user_id),
              updated_at = CURRENT_TIMESTAMP
            """,
            (project_id, session_id, user_id),
        )

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        row = await self._fetchone(
            """
            SELECT user_id
            FROM session_owners
            WHERE project_id = %s AND session_id = %s
            """,
            (project_id, session_id),
        )
        return str(row["user_id"]) if row else None

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        await self._execute(
            "DELETE FROM session_owners WHERE project_id = %s AND session_id = %s",
            (project_id, session_id),
        )

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        rows = await self._fetchall(
            """
            SELECT session_id
            FROM session_owners
            WHERE project_id = %s AND user_id = %s
            ORDER BY updated_at DESC, session_id ASC
            """,
            (project_id, user_id),
        )
        return [str(row["session_id"]) for row in rows]

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        if user_id is None:
            rows = await self._fetchall(
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = %s
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id,),
            )
        else:
            rows = await self._fetchall(
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = %s AND user_id = %s
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id, user_id),
            )
        return [_session_owner_record(row) for row in rows]


class ObArtifactAclStore(_ObStoreBase):
    """OceanBase MySQL-backed artifact ACL metadata store."""

    async def get_acl(self, *, artifact_type: str, slug: str) -> dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT acl_json
            FROM enterprise_artifact_acls
            WHERE artifact_type = %s AND slug = %s
            """,
            (artifact_type, slug),
        )
        if row is None:
            raise KeyError((artifact_type, slug))
        return _artifact_acl_record(row)

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict[str, Any]) -> dict[str, Any]:
        await self._execute(
            """
            INSERT INTO enterprise_artifact_acls (artifact_type, slug, acl_json, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                acl_json = VALUES(acl_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (artifact_type, slug, json.dumps(acl, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        )
        return await self.get_acl(artifact_type=artifact_type, slug=slug)


class ObAuditSink(_ObStoreBase):
    """OceanBase MySQL-backed audit sink and query reader."""

    async def write(self, event: AuditEvent) -> None:
        await self._execute(
            """
            INSERT INTO enterprise_audit_logs (
                user_id, action, resource_type, resource_id, decision, reason, request_id, metadata_json, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                event.user_id,
                event.action,
                event.resource_type,
                event.resource_id,
                event.decision,
                event.reason,
                event.request_id,
                json.dumps(event.metadata, ensure_ascii=False, sort_keys=True, default=str),
            ),
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
        request_id: str | None = None,
        before_id: int | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> list[AuditEvent]:
        where_sql, params = _where_mysql(
            {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "decision": decision,
                "request_id": request_id,
            }
        )
        if before_id is not None:
            where_sql, params = _append_where(where_sql, params, "id < %s", before_id)
        if created_after is not None:
            where_sql, params = _append_where(where_sql, params, "created_at >= %s", created_after)
        if created_before is not None:
            where_sql, params = _append_where(where_sql, params, "created_at < %s", created_before)
        params.append(max(1, int(limit)))
        rows = await self._fetchall(
            f"""
            SELECT id, user_id, action, resource_type, resource_id, decision, reason, request_id, metadata_json, created_at
            FROM enterprise_audit_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [_audit_event(row) for row in rows]


class ObEnterpriseQuotaStore(_ObStoreBase):
    """OceanBase MySQL-backed enterprise quota metadata and usage store."""

    async def list_quotas(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where_mysql({"subject_type": subject_type, "subject_id": subject_id, "resource": resource})
        rows = await self._fetchall(
            f"""
            SELECT subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
            FROM enterprise_quotas
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, resource ASC
            """,
            tuple(params),
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
        await self._execute(
            """
            INSERT INTO enterprise_quotas (
                subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                limit_value = VALUES(limit_value),
                window_seconds = VALUES(window_seconds),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (subject_type, subject_id, resource, int(limit), int(window_seconds), bool(enabled)),
        )
        quotas = await self.list_quotas(subject_type=subject_type, subject_id=subject_id, resource=resource)
        if not quotas:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise quota.")
        return quotas[0]

    async def list_usage(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        resource: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where_mysql({"subject_type": subject_type, "subject_id": subject_id, "resource": resource})
        rows = await self._fetchall(
            f"""
            SELECT subject_type, subject_id, resource, window_start, used, updated_at
            FROM enterprise_quota_usage
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, resource ASC, window_start DESC
            """,
            tuple(params),
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
        return await asyncio.to_thread(self._consume_quota_sync, normalized_subjects, resource, int(amount))

    def _consume_quota_sync(
        self,
        subjects: list[dict[str, str]],
        resource: str,
        amount: int,
    ) -> dict[str, Any]:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        clauses = " OR ".join(["(subject_type = %s AND subject_id = %s)"] * len(subjects))
        params: list[Any] = [resource]
        for subject in subjects:
            params.extend([subject["subject_type"], subject["subject_id"]])
        now = datetime.now(timezone.utc).replace(microsecond=0)

        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT subject_type, subject_id, resource, limit_value, window_seconds, enabled, created_at, updated_at
                    FROM enterprise_quotas
                    WHERE resource = %s AND enabled = 1 AND ({clauses})
                    ORDER BY subject_type ASC, subject_id ASC
                    FOR UPDATE
                    """,
                    tuple(params),
                )
                quota_rows = [dict(row) for row in cursor.fetchall()]
                applicable: list[tuple[dict[str, Any], dict[str, Any]]] = []
                for quota in quota_rows:
                    usage = _current_usage_for_quota_sync(cursor, quota, now)
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
                    cursor.execute(
                        """
                        INSERT INTO enterprise_quota_usage (
                            subject_type, subject_id, resource, window_start, used, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON DUPLICATE KEY UPDATE
                            used = used + VALUES(used),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            quota["subject_type"],
                            quota["subject_id"],
                            quota["resource"],
                            usage["window_start"],
                            amount,
                        ),
                    )
                    cursor.execute(
                        """
                        SELECT subject_type, subject_id, resource, window_start, used, updated_at
                        FROM enterprise_quota_usage
                        WHERE subject_type = %s AND subject_id = %s AND resource = %s AND window_start = %s
                        """,
                        (quota["subject_type"], quota["subject_id"], quota["resource"], usage["window_start"]),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        record = _quota_usage_record(row)
                        record["window_seconds"] = int(quota["window_seconds"])
                        updated_usage.append(record)
        return {"allowed": True, "usage": updated_usage}


class ObEnterpriseSecretStore(_ObStoreBase):
    """OceanBase MySQL-backed secret reference store.

    Only secret references are stored here. Secret values remain in the external
    provider named by each record.
    """

    async def list_secrets(self, *, prefix: str | None = None) -> list[dict[str, Any]]:
        if prefix is None:
            rows = await self._fetchall(
                """
                SELECT name, provider, reference, description, enabled, created_at, updated_at
                FROM enterprise_secrets
                ORDER BY name ASC
                """
            )
        else:
            rows = await self._fetchall(
                """
                SELECT name, provider, reference, description, enabled, created_at, updated_at
                FROM enterprise_secrets
                WHERE name LIKE %s ESCAPE '\\\\'
                ORDER BY name ASC
                """,
                (_like_prefix_pattern(prefix),),
            )
        return [_secret_record(row) for row in rows]

    async def get_secret(self, name: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT name, provider, reference, description, enabled, created_at, updated_at
            FROM enterprise_secrets
            WHERE name = %s
            """,
            (name,),
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
        await self._execute(
            """
            INSERT INTO enterprise_secrets (name, provider, reference, description, enabled, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                provider = VALUES(provider),
                reference = VALUES(reference),
                description = VALUES(description),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, provider, reference, description, bool(enabled)),
        )
        record = await self.get_secret(name)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise secret.")
        return record

    async def delete_secret(self, name: str) -> bool:
        return await self._execute("DELETE FROM enterprise_secrets WHERE name = %s", (name,)) > 0


class ObUserModelCredentialStore(_ObStoreBase):
    """OceanBase MySQL-backed per-user model credential store."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
        encryption_secret: str | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        secret = encryption_secret or os.getenv("DATUS_USER_MODEL_CREDENTIAL_SECRET")
        self._codec = CredentialSecretCodec(secret)
        self._user_model_credential_schema_ready = False

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        await self._ensure_user_model_credential_columns()
        rows = await self._fetchall(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = %s
            ORDER BY created_at ASC, credential_id ASC
            """,
            (user_id,),
        )
        return [_model_credential_record(row, self._codec) for row in rows]

    async def get_credential(self, user_id: str, credential_id: str) -> dict[str, Any] | None:
        await self._ensure_user_model_credential_columns()
        row = await self._fetchone(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = %s AND credential_id = %s
            """,
            (user_id, credential_id),
        )
        return _model_credential_record(row, self._codec) if row else None

    async def put_credential(
        self,
        *,
        user_id: str,
        credential_id: str,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        await self._ensure_user_model_credential_columns()
        await self._execute(
            """
            INSERT INTO user_model_credentials (
                user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                base_url, display_name, enabled, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                provider = VALUES(provider),
                model = VALUES(model),
                api_key_blob = VALUES(api_key_blob),
                api_key_hint = VALUES(api_key_hint),
                base_url = VALUES(base_url),
                display_name = VALUES(display_name),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                credential_id,
                provider,
                model,
                self._codec.encrypt(api_key),
                api_key_hint(api_key),
                base_url,
                display_name,
                bool(enabled),
            ),
        )
        record = await self.get_credential(user_id, credential_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist model credential.")
        return record

    async def _ensure_user_model_credential_columns(self) -> None:
        await asyncio.to_thread(self._ensure_user_model_credential_columns_sync)

    def _ensure_user_model_credential_columns_sync(self) -> None:
        if self._user_model_credential_schema_ready:
            return
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._schema_lock:
            if self._user_model_credential_schema_ready:
                return
            with self._pool.connection(database=self._config.database) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SHOW COLUMNS FROM user_model_credentials LIKE %s", ("base_url",))
                    if cursor.fetchone() is None:
                        cursor.execute("ALTER TABLE user_model_credentials ADD COLUMN base_url VARCHAR(512)")
            self._user_model_credential_schema_ready = True

    async def set_credential_enabled(
        self,
        user_id: str,
        credential_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        updated = await self._execute(
            """
            UPDATE user_model_credentials
            SET enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND credential_id = %s
            """,
            (bool(enabled), user_id, credential_id),
        )
        if updated == 0:
            return None
        return await self.get_credential(user_id, credential_id)

    async def delete_credential(self, user_id: str, credential_id: str) -> bool:
        deleted = await self._execute(
            "DELETE FROM user_model_credentials WHERE user_id = %s AND credential_id = %s",
            (user_id, credential_id),
        )
        await self._execute(
            """
            UPDATE user_model_preferences
            SET default_credential_id = NULL, default_model = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND default_credential_id = %s
            """,
            (user_id, credential_id),
        )
        return deleted > 0

    async def get_preference(self, user_id: str) -> dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT user_id, default_credential_id, default_model, created_at, updated_at
            FROM user_model_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return _model_preference_record(row) if row else _empty_model_preference(user_id)

    async def put_preference(
        self,
        *,
        user_id: str,
        default_credential_id: str | None,
        default_model: str | None,
    ) -> dict[str, Any]:
        await self._execute(
            """
            INSERT INTO user_model_preferences (
                user_id, default_credential_id, default_model, created_at, updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                default_credential_id = VALUES(default_credential_id),
                default_model = VALUES(default_model),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, default_credential_id, default_model),
        )
        return await self.get_preference(user_id)

    async def touch_credential_used(self, user_id: str, credential_id: str) -> None:
        await self._execute(
            """
            UPDATE user_model_credentials
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND credential_id = %s
            """,
            (user_id, credential_id),
        )


class ObUserDatasourceStore(_ObStoreBase):
    """OceanBase MySQL-backed per-user private datasource store."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
        encryption_secret: str | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        secret = encryption_secret or os.getenv("DATUS_USER_DATASOURCE_SECRET")
        self._datasource_codec = CredentialSecretCodec(secret)

    async def list_datasources(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = %s
            ORDER BY created_at ASC, datasource_id ASC
            """,
            (user_id,),
        )
        return [_user_datasource_record(row, self._datasource_codec) for row in rows]

    async def get_datasource(self, user_id: str, datasource_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = %s AND datasource_id = %s
            """,
            (user_id, datasource_id),
        )
        return _user_datasource_record(row, self._datasource_codec) if row else None

    async def put_datasource(
        self,
        *,
        user_id: str,
        datasource_id: str,
        datasource_type: str,
        host: str,
        port: str,
        username: str,
        password: str,
        database: str,
        display_name: str | None = None,
        schema: str | None = None,
        catalog: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        await self._execute(
            """
            INSERT INTO user_datasources (
                user_id, datasource_id, datasource_type, host, port, username, password_blob,
                password_hint, database_name, schema_name, catalog_name, display_name,
                enabled, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                datasource_type = VALUES(datasource_type),
                host = VALUES(host),
                port = VALUES(port),
                username = VALUES(username),
                password_blob = VALUES(password_blob),
                password_hint = VALUES(password_hint),
                database_name = VALUES(database_name),
                schema_name = VALUES(schema_name),
                catalog_name = VALUES(catalog_name),
                display_name = VALUES(display_name),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                datasource_id,
                datasource_type,
                host,
                port,
                username,
                self._datasource_codec.encrypt(password),
                password_hint(password),
                database,
                schema,
                catalog,
                display_name,
                bool(enabled),
            ),
        )
        record = await self.get_datasource(user_id, datasource_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist personal datasource.")
        return record

    async def set_datasource_enabled(
        self,
        user_id: str,
        datasource_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        updated = await self._execute(
            """
            UPDATE user_datasources
            SET enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND datasource_id = %s
            """,
            (bool(enabled), user_id, datasource_id),
        )
        if updated == 0:
            return None
        return await self.get_datasource(user_id, datasource_id)

    async def delete_datasource(self, user_id: str, datasource_id: str) -> bool:
        return (
            await self._execute(
                "DELETE FROM user_datasources WHERE user_id = %s AND datasource_id = %s",
                (user_id, datasource_id),
            )
            > 0
        )

    async def touch_datasource_used(self, user_id: str, datasource_id: str) -> None:
        await self._execute(
            """
            UPDATE user_datasources
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND datasource_id = %s
            """,
            (user_id, datasource_id),
        )


def _replace_role_permissions_sync(cursor: Any, role_id: str, permissions: list[str]) -> None:
    cursor.execute("DELETE FROM enterprise_role_permissions WHERE role_id = %s", (role_id,))
    normalized = _normalized_strings(permissions)
    if normalized:
        cursor.executemany(
            """
            INSERT INTO enterprise_role_permissions (role_id, permission)
            VALUES (%s, %s)
            """,
            [(role_id, permission) for permission in normalized],
        )


def _current_usage_for_quota_sync(cursor: Any, quota: dict[str, Any], now: datetime) -> dict[str, Any]:
    window_floor = now - timedelta(seconds=int(quota["window_seconds"]))
    cursor.execute(
        """
        SELECT subject_type, subject_id, resource, window_start, used, updated_at
        FROM enterprise_quota_usage
        WHERE subject_type = %s
            AND subject_id = %s
            AND resource = %s
            AND window_start > %s
        ORDER BY window_start DESC
        LIMIT 1
        FOR UPDATE
        """,
        (quota["subject_type"], quota["subject_id"], quota["resource"], window_floor),
    )
    row = cursor.fetchone()
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


def _where_mysql(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses = []
    params = []
    for column, value in filters.items():
        if value is None:
            continue
        clauses.append(f"{column} = %s")
        params.append(value)
    if not clauses:
        return "", params
    return f"WHERE {' AND '.join(clauses)}", params


def _append_where(where_sql: str, params: list[Any], clause: str, value: Any) -> tuple[str, list[Any]]:
    params.append(value)
    if where_sql:
        return f"{where_sql} AND {clause}", params
    return f"WHERE {clause}", params


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


def _load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _load_json_dict(value: Any) -> dict[str, Any]:
    loaded = _load_json(value)
    return loaded if isinstance(loaded, dict) else {}


def _load_json_list(value: Any) -> list[str]:
    loaded = _load_json(value)
    return _normalized_strings(loaded if isinstance(loaded, list) else [])


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
        "external_user_id": _optional_str(row["external_user_id"]),
        "department": _optional_str(row["department"]),
        "title": _optional_str(row["title"]),
        "last_seen_at": _iso(row["last_seen_at"]),
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
        "scope": _normalized_grant_scope(_load_json_dict(row["scope_json"])),
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
        "tools": _load_json_list(row["tools_json"]),
        "mcp": _load_json_list(row["mcp_json"]),
        "skills": _load_json_list(row["skills_json"]),
        "scoped_context": _load_json_dict(row["scoped_context_json"]),
        "rules": _load_json_list(row["rules_json"]),
        "max_turns": int(row["max_turns"] or 30),
        "acl": _normalized_agent_acl(_load_json_dict(row["acl_json"])),
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
        id=int(row["id"]) if row["id"] is not None else None,
        user_id=_optional_str(row["user_id"]),
        action=str(row["action"]),
        resource_type=str(row["resource_type"]),
        resource_id=_optional_str(row["resource_id"]),
        decision=str(row["decision"]),
        reason=_optional_str(row["reason"]),
        request_id=_optional_str(row["request_id"]),
        created_at=_iso(row["created_at"]),
        metadata=_load_json_dict(row["metadata_json"]),
    )


def _artifact_acl_record(row: Any) -> dict[str, Any]:
    return _load_json_dict(row["acl_json"])


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


def _model_credential_record(row: Any, codec: CredentialSecretCodec) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "id": str(row["credential_id"]),
        "provider": str(row["provider"]),
        "model": str(row["model"]),
        "api_key": codec.decrypt(str(row["api_key_blob"])),
        "base_url": _optional_str(row["base_url"]),
        "ref_hint": str(row["api_key_hint"]),
        "display_name": _optional_str(row["display_name"]),
        "enabled": bool(row["enabled"]),
        "last_used_at": _iso(row["last_used_at"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _empty_model_preference(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "default_credential_id": None,
        "default_model": None,
        "created_at": None,
        "updated_at": None,
    }


def _model_preference_record(row: Any) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "default_credential_id": _optional_str(row["default_credential_id"]),
        "default_model": _optional_str(row["default_model"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _user_datasource_record(row: Any, codec: CredentialSecretCodec) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "id": str(row["datasource_id"]),
        "type": str(row["datasource_type"]),
        "host": str(row["host"]),
        "port": str(row["port"]),
        "username": str(row["username"]),
        "password": codec.decrypt(str(row["password_blob"])),
        "password_hint": str(row["password_hint"]),
        "database": str(row["database_name"]),
        "schema": _optional_str(row["schema_name"]),
        "catalog": _optional_str(row["catalog_name"]),
        "display_name": _optional_str(row["display_name"]),
        "enabled": bool(row["enabled"]),
        "last_used_at": _iso(row["last_used_at"]),
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
    return to_utc_iso(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


_AGENT_COLUMNS = """
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
tools_json,
mcp_json,
skills_json,
scoped_context_json,
rules_json,
max_turns,
acl_json,
created_at,
updated_at
"""


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_users (
  user_id VARCHAR(255) NOT NULL,
  display_name VARCHAR(255),
  email VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  external_user_id VARCHAR(255),
  department VARCHAR(255),
  title VARCHAR(255),
  last_seen_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  INDEX idx_enterprise_users_enabled (enabled, user_id)
);

CREATE TABLE IF NOT EXISTS enterprise_roles (
  role_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description LONGTEXT,
  built_in TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id)
);

CREATE TABLE IF NOT EXISTS enterprise_role_permissions (
  role_id VARCHAR(255) NOT NULL,
  permission VARCHAR(255) NOT NULL,
  PRIMARY KEY (role_id, permission)
);

CREATE TABLE IF NOT EXISTS enterprise_user_roles (
  user_id VARCHAR(255) NOT NULL,
  role_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, role_id),
  INDEX idx_enterprise_user_roles_role (role_id, user_id)
);

CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  datasource_key VARCHAR(255) NOT NULL,
  effect VARCHAR(16) NOT NULL,
  scope_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, datasource_key),
  INDEX idx_enterprise_datasource_grants_datasource (datasource_key, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS enterprise_agents (
  agent_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description LONGTEXT,
  node_class VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  owner_user_id VARCHAR(255),
  datasource_id VARCHAR(255),
  artifact_slug VARCHAR(255),
  prompt_template LONGTEXT,
  prompt_language VARCHAR(32) NOT NULL DEFAULT 'en',
  prompt_version VARCHAR(64) NOT NULL DEFAULT '1.0',
  tools_json LONGTEXT NOT NULL,
  mcp_json LONGTEXT NOT NULL,
  skills_json LONGTEXT NOT NULL,
  scoped_context_json LONGTEXT NOT NULL,
  rules_json LONGTEXT NOT NULL,
  max_turns INTEGER NOT NULL DEFAULT 30,
  acl_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (agent_id),
  INDEX idx_enterprise_agents_status (status, agent_id),
  INDEX idx_enterprise_agents_owner (owner_user_id, agent_id)
);

CREATE TABLE IF NOT EXISTS session_owners (
  project_id VARCHAR(255) NOT NULL,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, session_id),
  INDEX idx_session_owners_user (project_id, user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS enterprise_artifact_acls (
  artifact_type VARCHAR(64) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  acl_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (artifact_type, slug)
);

CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(255),
  action VARCHAR(255) NOT NULL,
  resource_type VARCHAR(128) NOT NULL,
  resource_id VARCHAR(255),
  decision VARCHAR(64) NOT NULL,
  reason LONGTEXT,
  request_id VARCHAR(255),
  metadata_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_audit_created (id, created_at),
  INDEX idx_enterprise_audit_user_action (user_id, action, id),
  INDEX idx_enterprise_audit_request (request_id, id),
  INDEX idx_enterprise_audit_created_at (created_at, id)
);

CREATE TABLE IF NOT EXISTS enterprise_quotas (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  resource VARCHAR(255) NOT NULL,
  limit_value BIGINT NOT NULL,
  window_seconds BIGINT NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, resource)
);

CREATE TABLE IF NOT EXISTS enterprise_quota_usage (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  resource VARCHAR(255) NOT NULL,
  window_start TIMESTAMP NOT NULL,
  used BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, resource, window_start),
  INDEX idx_enterprise_quota_usage_resource (resource, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS enterprise_secrets (
  name VARCHAR(255) NOT NULL,
  provider VARCHAR(128) NOT NULL,
  reference LONGTEXT NOT NULL,
  description LONGTEXT,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (name),
  INDEX idx_enterprise_secrets_enabled (enabled, name)
);

CREATE TABLE IF NOT EXISTS user_model_credentials (
  user_id VARCHAR(255) NOT NULL,
  credential_id VARCHAR(255) NOT NULL,
  provider VARCHAR(128) NOT NULL,
  model VARCHAR(255) NOT NULL,
  api_key_blob LONGTEXT NOT NULL,
  api_key_hint VARCHAR(32) NOT NULL,
  base_url VARCHAR(512),
  display_name VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  last_used_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, credential_id),
  INDEX idx_user_model_credentials_user_enabled (user_id, enabled, created_at)
);

CREATE TABLE IF NOT EXISTS user_model_preferences (
  user_id VARCHAR(255) NOT NULL,
  default_credential_id VARCHAR(255),
  default_model VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS user_datasources (
  user_id VARCHAR(255) NOT NULL,
  datasource_id VARCHAR(255) NOT NULL,
  datasource_type VARCHAR(128) NOT NULL,
  host VARCHAR(255) NOT NULL,
  port VARCHAR(32) NOT NULL,
  username VARCHAR(255) NOT NULL,
  password_blob LONGTEXT NOT NULL,
  password_hint VARCHAR(32) NOT NULL,
  database_name VARCHAR(255) NOT NULL,
  schema_name VARCHAR(255),
  catalog_name VARCHAR(255),
  display_name VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  last_used_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, datasource_id),
  INDEX idx_user_datasources_user_enabled (user_id, enabled, created_at)
);
"""

"""OceanBase ownership, ACL, audit, quota, and secret metadata stores."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from datus.api.enterprise.models import AuditEvent
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.common.normalization import _like_prefix_pattern, _normalized_quota_subjects
from datus_enterprise.storage.oceanbase.base import _ObStoreBase
from datus_enterprise.storage.oceanbase.records import (
    _append_where,
    _artifact_acl_record,
    _audit_event,
    _current_usage_for_quota_sync,
    _iso,
    _quota_record,
    _quota_usage_record,
    _secret_record,
    _session_owner_record,
    _where_mysql,
)
from datus_enterprise.storage.oceanbase.schema import _SCHEMA_SQL


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

    async def get_session(self, project_id: str, session_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE project_id = %s AND session_id = %s
            """,
            (project_id, session_id),
        )
        return _session_owner_record(row) if row else None

    async def get_sessions(self, project_id: str, session_ids: list[str]) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        placeholders = ", ".join("%s" for _ in session_ids)
        rows = await self._fetchall(
            f"""
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE project_id = %s AND session_id IN ({placeholders})
            """,
            (project_id, *session_ids),
        )
        return [_session_owner_record(row) for row in rows]

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

    async def list_sessions_page(
        self,
        project_id: str,
        user_id: str | None = None,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [project_id]
        where = "project_id = %s"
        if user_id is not None:
            where += " AND user_id = %s"
            params.append(user_id)
        params.extend((int(limit), int(offset)))
        rows = await self._fetchall(
            f"""
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE {where}
            ORDER BY updated_at DESC, session_id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
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

    async def delete_quota(self, *, subject_type: str, subject_id: str, resource: str) -> bool:
        return await asyncio.to_thread(self._delete_quota_sync, subject_type, subject_id, resource)

    def _delete_quota_sync(self, subject_type: str, subject_id: str, resource: str) -> bool:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM enterprise_quota_usage
                    WHERE subject_type = %s AND subject_id = %s AND resource = %s
                    """,
                    (subject_type, subject_id, resource),
                )
                cursor.execute(
                    """
                    DELETE FROM enterprise_quotas
                    WHERE subject_type = %s AND subject_id = %s AND resource = %s
                    """,
                    (subject_type, subject_id, resource),
                )
                return int(cursor.rowcount or 0) > 0

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

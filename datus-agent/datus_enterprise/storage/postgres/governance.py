"""PostgreSQL ownership, ACL, audit, quota, and secret metadata stores."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from datus.api.enterprise.models import AuditEvent
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.common.normalization import _like_prefix_pattern, _normalized_quota_subjects
from datus_enterprise.storage.postgres.base import _PgStoreBase
from datus_enterprise.storage.postgres.records import (
    _affected_rows,
    _artifact_acl_record,
    _audit_event,
    _iso,
    _quota_record,
    _quota_usage_record,
    _secret_record,
    _session_owner_record,
    _where,
)


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

    async def get_session(self, project_id: str, session_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE project_id = $1 AND session_id = $2
            """,
            project_id,
            session_id,
        )
        return _session_owner_record(row) if row else None

    async def get_sessions(self, project_id: str, session_ids: list[str]) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        rows = await self._fetch(
            """
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE project_id = $1 AND session_id = ANY($2::text[])
            """,
            project_id,
            session_ids,
        )
        return [_session_owner_record(row) for row in rows]

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

    async def list_sessions_page(
        self,
        project_id: str,
        user_id: str | None = None,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [project_id]
        filters = ["project_id = $1"]
        if user_id is not None:
            params.append(user_id)
            filters.append(f"user_id = ${len(params)}")
        params.extend((int(limit), int(offset)))
        rows = await self._fetch(
            f"""
            SELECT project_id, session_id, user_id, created_at, updated_at
            FROM session_owners
            WHERE {" AND ".join(filters)}
            ORDER BY updated_at DESC, session_id ASC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
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

    async def delete_acl(self, *, artifact_type: str, slug: str) -> None:
        await self._execute(
            """
            DELETE FROM enterprise_artifact_acls
            WHERE artifact_type = $1 AND slug = $2
            """,
            artifact_type,
            slug,
        )


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
        request_id: str | None = None,
        before_id: int | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> list[AuditEvent]:
        filters = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "decision": decision,
            "request_id": request_id,
        }
        where_sql, params = _where(filters)
        if before_id is not None:
            params.append(before_id)
            before_clause = f"id < ${len(params)}"
            where_sql = f"{where_sql} AND {before_clause}" if where_sql else f"WHERE {before_clause}"
        if created_after is not None:
            params.append(created_after)
            created_after_clause = f"created_at >= ${len(params)}::timestamptz"
            where_sql = f"{where_sql} AND {created_after_clause}" if where_sql else f"WHERE {created_after_clause}"
        if created_before is not None:
            params.append(created_before)
            created_before_clause = f"created_at < ${len(params)}::timestamptz"
            where_sql = f"{where_sql} AND {created_before_clause}" if where_sql else f"WHERE {created_before_clause}"
        params.append(max(1, int(limit)))
        rows = await self._fetch(
            f"""
            SELECT id, user_id, action, resource_type, resource_id, decision, reason, request_id, metadata_json, created_at
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

    async def delete_quota(self, *, subject_type: str, subject_id: str, resource: str) -> bool:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    DELETE FROM enterprise_quota_usage
                    WHERE subject_type = $1 AND subject_id = $2 AND resource = $3
                    """,
                    subject_type,
                    subject_id,
                    resource,
                )
                result = await conn.execute(
                    """
                    DELETE FROM enterprise_quotas
                    WHERE subject_type = $1 AND subject_id = $2 AND resource = $3
                    """,
                    subject_type,
                    subject_id,
                    resource,
                )
        return _affected_rows(result) > 0

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

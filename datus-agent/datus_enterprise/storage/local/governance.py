"""Local quota, secret-reference, and audit stores."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from datus.utils.exceptions import DatusException, ErrorCode

if TYPE_CHECKING:
    from datus.api.enterprise.models import AuditEvent

from datus_enterprise.storage.local.common import (
    _audit_event_from_row,
    _copy_quota_record,
    _copy_secret_record,
    _normalized_quota_subjects,
    _offload_sqlite_async_methods,
    _parse_datetime,
    _quota_filter_matches,
    _sqlite_now,
)


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

    async def delete_quota(self, *, subject_type: str, subject_id: str, resource: str) -> bool:
        key = (subject_type, subject_id, resource)
        deleted = self._quotas.pop(key, None) is not None
        self._usage.pop(key, None)
        return deleted

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

    async def consume_quota(
        self,
        *,
        subjects: list[dict[str, str]],
        resource: str,
        amount: int = 1,
    ) -> dict[str, Any]:
        """Check and consume all enabled quotas matching ``subjects`` and ``resource``."""

        if amount <= 0:
            raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Quota consume amount must be positive.")
        normalized_subjects = _normalized_quota_subjects(subjects)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        applicable: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for subject in normalized_subjects:
            quota = self._quotas.get((subject["subject_type"], subject["subject_id"], resource))
            if quota is None or not bool(quota.get("enabled", True)):
                continue
            usage = self._current_usage_for_quota(quota, now)
            if int(usage["used"]) + amount > int(quota["limit"]):
                return {
                    "allowed": False,
                    "reason": "quota exceeded",
                    "subject_type": quota["subject_type"],
                    "subject_id": quota["subject_id"],
                    "resource": quota["resource"],
                    "limit": int(quota["limit"]),
                    "used": int(usage["used"]),
                    "remaining": max(int(quota["limit"]) - int(usage["used"]), 0),
                    "window_start": usage["window_start"],
                    "window_seconds": int(quota["window_seconds"]),
                }
            applicable.append((quota, usage))

        updated_usage = []
        for quota, usage in applicable:
            usage["used"] = int(usage["used"]) + amount
            usage["updated_at"] = now.isoformat()
            self._usage[(quota["subject_type"], quota["subject_id"], quota["resource"])] = usage
            updated_usage.append(copy.deepcopy(usage))

        return {"allowed": True, "usage": updated_usage}

    def _current_usage_for_quota(self, quota: dict[str, Any], now: datetime) -> dict[str, Any]:
        key = (quota["subject_type"], quota["subject_id"], quota["resource"])
        usage = self._usage.get(key)
        if usage is not None:
            window_start = _parse_datetime(usage.get("window_start"))
            if window_start is not None and (now - window_start).total_seconds() < int(quota["window_seconds"]):
                return copy.deepcopy(usage)
        now_text = now.isoformat()
        return {
            "subject_type": quota["subject_type"],
            "subject_id": quota["subject_id"],
            "resource": quota["resource"],
            "used": 0,
            "window_start": now_text,
            "window_seconds": int(quota["window_seconds"]),
            "updated_at": now_text,
        }


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


class NoopAuditSink:
    """No-op audit sink for local/open-source mode."""

    async def write(self, event: AuditEvent) -> None:  # noqa: ARG002
        return None


@_offload_sqlite_async_methods
class SqliteAuditSink:
    """SQLite-backed audit sink for single-node enterprise MVP deployments."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def write(self, event: AuditEvent) -> None:
        with self._connect() as conn:
            conn.execute(
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _sqlite_now(),
                ),
            )
            conn.commit()

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
        where = []
        params: list[Any] = []
        for column, value in filters.items():
            if value is None:
                continue
            where.append(f"{column} = ?")
            params.append(value)
        if before_id is not None:
            where.append("id < ?")
            params.append(before_id)
        if created_after is not None:
            where.append("created_at >= ?")
            params.append(created_after)
        if created_before is not None:
            where.append("created_at < ?")
            params.append(created_before)

        query = """
            SELECT id, user_id, action, resource_type, resource_id, decision, reason, request_id, metadata_json, created_at
            FROM enterprise_audit_logs
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, int(limit)))

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [_audit_event_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    request_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_filter
                ON enterprise_audit_logs (user_id, action, resource_type, resource_id, decision, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_request_id
                ON enterprise_audit_logs (request_id, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_created_at
                ON enterprise_audit_logs (created_at, id)
                """
            )
            conn.commit()

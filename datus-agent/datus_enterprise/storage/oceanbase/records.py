"""Record conversion and input normalization for OceanBase metadata stores."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from datus.api.enterprise.models import AuditEvent
from datus.api.enterprise.prompt_versions import prompt_template_value
from datus.utils.time_utils import to_utc_iso
from datus_enterprise.model_credentials import CredentialSecretCodec
from datus_enterprise.storage.common.normalization import (
    _normalized_agent_acl,
    _normalized_agent_status,
    _normalized_grant_effect,
    _normalized_grant_scope,
    _normalized_strings,
    _optional_str,
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


def _chat_preference_record(row: Any | None, *, user_id: str) -> dict[str, Any]:
    if row is None:
        return {
            "user_id": user_id,
            "default_agent_id": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "user_id": str(row["user_id"]),
        "default_agent_id": _optional_str(row.get("default_agent_id")),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
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
        "prompt_template": prompt_template_value(row["prompt_template"]),
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


def _prompt_version_record(row: Any) -> dict[str, Any]:
    return {
        "version_id": str(row["version_id"]),
        "agent_id": str(row["agent_id"]),
        "version": str(row["version_label"]),
        "prompt_template": str(row["prompt_template"]),
        "prompt_language": str(row["prompt_language"] or "en"),
        "content_sha256": str(row["content_sha256"]),
        "change_note": _optional_str(row["change_note"]),
        "based_on_version_id": _optional_str(row["based_on_version_id"]),
        "created_by": _optional_str(row["created_by"]),
        "created_at": _iso(row["created_at"]),
        "active": bool(row["active"]),
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

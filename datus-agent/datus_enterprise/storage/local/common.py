"""Shared SQLite and record helpers for local enterprise stores."""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode

_SQLITE_WORKER_ACTIVE: ContextVar[bool] = ContextVar("enterprise_sqlite_worker_active", default=False)


def _offload_sqlite_async_methods(cls):
    """Run a SQLite store's async protocol methods outside the API event loop."""

    for name, method in list(cls.__dict__.items()):
        if asyncio.iscoroutinefunction(method):
            setattr(cls, name, _sqlite_thread_wrapper(method))
    return cls


def _sqlite_thread_wrapper(method):
    @functools.wraps(method)
    async def wrapped(*args, **kwargs):
        if _SQLITE_WORKER_ACTIVE.get():
            return await method(*args, **kwargs)

        def run_in_worker():
            token = _SQLITE_WORKER_ACTIVE.set(True)
            try:
                return asyncio.run(method(*args, **kwargs))
            finally:
                _SQLITE_WORKER_ACTIVE.reset(token)

        return await asyncio.to_thread(run_in_worker)

    return wrapped


def _sqlite_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_sqlite_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def _audit_event_from_row(row):
    from datus.api.enterprise.models import AuditEvent

    metadata: dict[str, Any]
    try:
        raw_metadata = json.loads(row[8] or "{}")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    except json.JSONDecodeError:
        metadata = {}
    return AuditEvent(
        id=int(row[0]) if row[0] is not None else None,
        user_id=_optional_str(row[1]),
        action=str(row[2]),
        resource_type=str(row[3]),
        resource_id=_optional_str(row[4]),
        decision=str(row[5]),
        reason=_optional_str(row[6]),
        request_id=_optional_str(row[7]),
        created_at=_optional_str(row[9]),
        metadata=metadata,
    )


def _copy_user_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(record["user_id"]),
        "display_name": _optional_str(record.get("display_name")),
        "email": _optional_str(record.get("email")),
        "enabled": bool(record.get("enabled")),
        "external_user_id": _optional_str(record.get("external_user_id")),
        "department": _optional_str(record.get("department")),
        "title": _optional_str(record.get("title")),
        "last_seen_at": _optional_str(record.get("last_seen_at")),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _empty_chat_preference(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "default_agent_id": None,
        "created_at": None,
        "updated_at": None,
    }


def _user_record_from_row(row) -> dict[str, Any]:
    return {
        "user_id": str(row[0]),
        "display_name": _optional_str(row[1]),
        "email": _optional_str(row[2]),
        "enabled": bool(row[3]),
        "external_user_id": _optional_str(row[4]),
        "department": _optional_str(row[5]),
        "title": _optional_str(row[6]),
        "last_seen_at": _optional_str(row[7]),
        "created_at": _optional_str(row[8]),
        "updated_at": _optional_str(row[9]),
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


def _normalized_agent_status(status: Any) -> str:
    normalized = str(status or "draft").strip().lower()
    if normalized not in {"draft", "published", "disabled", "archived"}:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"Invalid agent status: {status!r}.")
    return normalized


def _normalized_agent_acl(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    visibility = str(raw.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "role", "enterprise"}:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"Invalid agent visibility: {visibility!r}.")
    allowed_roles = sorted({str(item).strip() for item in raw.get("allowed_roles") or [] if str(item).strip()})
    allowed_user_ids = sorted({str(item).strip() for item in raw.get("allowed_user_ids") or [] if str(item).strip()})
    return {
        "visibility": visibility,
        "allowed_roles": allowed_roles,
        "allowed_user_ids": allowed_user_ids,
    }


def _normalized_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = value
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _normalized_agent_record(record: dict[str, Any]) -> dict[str, Any]:
    from datus.api.enterprise.prompt_versions import prompt_template_value

    agent_id = str(record["agent_id"]).strip()
    return {
        "agent_id": agent_id,
        "name": str(record.get("name") or agent_id).strip(),
        "description": _optional_str(record.get("description")),
        "node_class": str(record.get("node_class") or record.get("type") or "gen_sql").strip(),
        "status": _normalized_agent_status(record.get("status")),
        "owner_user_id": _optional_str(record.get("owner_user_id")),
        "datasource_id": _optional_str(record.get("datasource_id")),
        "artifact_slug": _optional_str(record.get("artifact_slug")),
        "prompt_template": prompt_template_value(record.get("prompt_template")),
        "prompt_language": str(record.get("prompt_language") or "en").strip(),
        "prompt_version": _optional_str(record.get("prompt_version")) or "1.0",
        "tools": _normalized_string_list(record.get("tools")),
        "mcp": _normalized_string_list(record.get("mcp")),
        "skills": _normalized_string_list(record.get("skills")),
        "scoped_context": copy.deepcopy(record.get("scoped_context") or {}),
        "rules": _normalized_string_list(record.get("rules")),
        "max_turns": int(record.get("max_turns") or 30),
        "acl": _normalized_agent_acl(record.get("acl")),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _copy_agent_record(record: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(_normalized_agent_record(record))


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


def _copy_model_credential_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(record["user_id"]),
        "id": str(record["id"]),
        "provider": str(record["provider"]),
        "model": str(record["model"]),
        "api_key": str(record["api_key"]),
        "base_url": _optional_str(record.get("base_url")),
        "ref_hint": str(record["ref_hint"]),
        "display_name": _optional_str(record.get("display_name")),
        "enabled": bool(record["enabled"]),
        "last_used_at": _optional_str(record.get("last_used_at")),
        "created_at": _optional_str(record.get("created_at")),
        "updated_at": _optional_str(record.get("updated_at")),
    }


def _api_key_hint(api_key: str) -> str:
    if len(api_key) <= 4:
        return "***"
    return f"***{api_key[-4:]}"


def _empty_model_preference(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "default_credential_id": None,
        "default_model": None,
        "created_at": None,
        "updated_at": None,
    }


def _model_preference_from_row(row) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "default_credential_id": _optional_str(row["default_credential_id"]),
        "default_model": _optional_str(row["default_model"]),
        "created_at": _optional_str(row["created_at"]),
        "updated_at": _optional_str(row["updated_at"]),
    }


def _copy_user_datasource_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(record["user_id"]),
        "id": str(record["id"]),
        "type": str(record["type"]),
        "host": str(record["host"]),
        "port": str(record["port"]),
        "username": str(record["username"]),
        "password": str(record["password"]),
        "password_hint": str(record["password_hint"]),
        "database": str(record["database"]),
        "schema": _optional_str(record.get("schema")),
        "catalog": _optional_str(record.get("catalog")),
        "display_name": _optional_str(record.get("display_name")),
        "enabled": bool(record["enabled"]),
        "last_used_at": _optional_str(record.get("last_used_at")),
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


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _grant_matches_search(record: dict[str, Any], search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    values = (
        record.get("subject_type"),
        record.get("subject_id"),
        record.get("datasource_key"),
        record.get("effect"),
        json.dumps(record.get("scope") or {}, ensure_ascii=False, sort_keys=True),
    )
    return any(query in str(value or "").casefold() for value in values)


def _sqlite_like_contains_pattern(value: str) -> str:
    escaped = value.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


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
        patterns = _normalized_grant_scope_patterns(values, key)
        if patterns:
            normalized[key] = patterns
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

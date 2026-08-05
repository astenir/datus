"""Database-independent enterprise record normalization."""

from __future__ import annotations

from typing import Any

from datus.api.enterprise.prompt_versions import prompt_template_value
from datus.utils.exceptions import DatusException, ErrorCode


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
        "prompt_template": prompt_template_value(record.get("prompt_template")),
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


def _like_prefix_pattern(prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def _like_contains_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None

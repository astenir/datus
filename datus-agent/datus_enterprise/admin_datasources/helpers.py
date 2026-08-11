"""Shared non-route helpers for enterprise datasource administration."""

from __future__ import annotations

import json
from typing import Any

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.utils.loggings import get_logger
from datus_enterprise.admin_datasources.models import (
    AdminDatasourceGrantSubjectSummary,
    AdminDatasourceGrantSummary,
)
from datus_enterprise.audit import AuditEvent, audit_decision

logger = get_logger(__name__)


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


def _grant_role_subject_matches_search(record: dict[str, Any], search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    return any(query in str(record.get(field) or "").casefold() for field in ("role_id", "name"))


def _grant_subject_summary_from_record(
    record: dict[str, Any],
    *,
    subject_type: str,
) -> AdminDatasourceGrantSubjectSummary:
    if subject_type == "user":
        return AdminDatasourceGrantSubjectSummary(
            subject_type="user",
            subject_id=str(record["user_id"]),
            display_name=_optional_str(record.get("display_name")),
            enabled=bool(record.get("enabled", True)),
        )
    return AdminDatasourceGrantSubjectSummary(
        subject_type="role",
        subject_id=str(record["role_id"]),
        display_name=_optional_str(record.get("name")),
    )


def _default_datasource_name(svc: ServiceDep) -> str | None:
    current = getattr(svc.agent_config, "current_datasource", None)
    if current:
        return str(current)
    default = getattr(svc.agent_config.services, "default_datasource", None)
    return str(default) if default else None


def _datasource_type(config) -> str | None:
    if isinstance(config, dict):
        value = config.get("type")
    else:
        value = getattr(config, "type", None)
    return str(value) if value is not None else None


def _datasource_display_name(config) -> str | None:
    if isinstance(config, dict):
        value = config.get("display_name")
    else:
        value = getattr(config, "display_name", None)
    text = str(value).strip() if value is not None else ""
    return text or None


async def _validate_existing_grant_subject(
    ctx: AppContext,
    *,
    subject_type: str,
    subject_id: str,
    datasource_key: str,
) -> Result[Any] | None:
    extensions = deps.get_enterprise_extensions()
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if subject_type == "user":
        try:
            user = await extensions.user_store.get_user(subject_id)
        except Exception:
            await _audit_datasource_grant(
                ctx,
                operation="upsert_admin_datasource_grant",
                decision="deny",
                reason="user read failed",
                resource_id=resource_id,
            )
            return _datasource_error("USER_READ_FAILED", "User read failed.")
        if user is None:
            await _audit_datasource_grant(
                ctx,
                operation="upsert_admin_datasource_grant",
                decision="deny",
                reason="user not found",
                resource_id=resource_id,
            )
            return _datasource_error("RESOURCE_NOT_FOUND", "User not found.")
        return None

    try:
        role = await extensions.role_store.get_role(subject_id)
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="role read failed",
            resource_id=resource_id,
        )
        return _datasource_error("ROLE_READ_FAILED", "Role read failed.")
    if role is None:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="role not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Role not found.")
    return None


async def _audit_datasource_grant(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    reason: str | None = None,
    resource_id: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"operation": operation}
    if old_summary is not None:
        audit_metadata["old"] = old_summary
    if new_summary is not None:
        audit_metadata["new"] = new_summary
    if metadata:
        audit_metadata.update(metadata)
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource_grant",
            resource_id=resource_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


async def _audit_datasource_grant_best_effort(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    reason: str | None = None,
    resource_id: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await _audit_datasource_grant(
            ctx,
            operation=operation,
            decision=decision,
            reason=reason,
            resource_id=resource_id,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Admin datasource grant audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


async def _audit_decision_best_effort(
    ctx: AppContext,
    event: AuditEvent,
    *,
    operation: str,
    decision: str,
) -> None:
    try:
        await audit_decision(ctx, event)
    except Exception as exc:
        logger.warning(
            "Admin datasource audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


def _grant_summary_from_record(record: dict[str, Any]) -> AdminDatasourceGrantSummary:
    return AdminDatasourceGrantSummary(
        subject_type=str(record["subject_type"]),
        subject_id=str(record["subject_id"]),
        datasource_key=str(record["datasource_key"]),
        effect=str(record["effect"]),
        scope=_normalized_scope(record.get("scope") or {}),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _grant_summary_for_audit(summary: AdminDatasourceGrantSummary) -> dict[str, Any]:
    return {
        "subject_type": summary.subject_type,
        "subject_id": summary.subject_id,
        "datasource_key": summary.datasource_key,
        "effect": summary.effect,
        "scope": dict(summary.scope),
    }


def _grant_record_for_audit(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return _grant_summary_for_audit(_grant_summary_from_record(record))


def _validate_optional_grant_filters(
    *,
    subject_type: str | None,
    subject_id: str | None,
    datasource_key: str | None,
) -> str | None:
    if subject_type is not None and subject_type not in {"user", "role"}:
        return "Invalid subject_type. Only user and role are supported."
    if subject_id is not None:
        invalid_subject = _validate_subject_id(subject_id, subject_type or "user")
        if invalid_subject is not None:
            return invalid_subject
    if datasource_key is not None:
        return _validate_datasource_key(datasource_key)
    return None


def _validate_grant_identity(*, subject_type: str, subject_id: str, datasource_key: str) -> str | None:
    if subject_type not in {"user", "role"}:
        return "Invalid subject_type. Only user and role are supported."
    return _validate_subject_id(subject_id, subject_type) or _validate_datasource_key(datasource_key)


def _validate_subject_id(subject_id: str, subject_type: str) -> str | None:
    candidate = subject_id.strip()
    if candidate != subject_id or not candidate or not USER_ID_PATTERN.fullmatch(subject_id):
        return f"Invalid {subject_type}_id. Only letters, digits, underscore and hyphen are allowed."
    return None


def _validate_datasource_key(datasource_key: str) -> str | None:
    candidate = datasource_key.strip()
    if candidate != datasource_key or not candidate or "/" in datasource_key or len(datasource_key) > 128:
        return "Invalid datasource_key. It cannot be empty, contain slash, or exceed 128 characters."
    return None


def _validate_grant_scope(scope: dict[str, Any]) -> str | None:
    try:
        _normalized_scope(scope)
    except ValueError as exc:
        return str(exc)
    return None


def _validate_grant_effect(effect: Any) -> str | None:
    if not isinstance(effect, str):
        return "Datasource grant effect must be a string."
    candidate = effect.strip().lower()
    if candidate != effect or candidate not in {"allow", "deny"}:
        return "Datasource grant effect must be allow or deny."
    return None


def _normalized_effect(effect: str) -> str:
    return effect.strip().lower()


def _normalized_scope(scope: Any) -> dict[str, Any]:
    if not isinstance(scope, dict):
        raise ValueError("Datasource grant scope must be a mapping.")
    allowed_keys = {"allow_catalog", "allow_sql", "catalogs", "databases", "schemas", "tables"}
    unknown_keys = sorted(set(scope) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"Unsupported datasource grant scope key: {unknown_keys[0]}.")

    normalized: dict[str, Any] = {}
    for key in ("allow_catalog", "allow_sql"):
        if key not in scope:
            continue
        if not isinstance(scope[key], bool):
            raise ValueError(f"Datasource grant scope.{key} must be a boolean.")
        normalized[key] = scope[key]

    for key in ("catalogs", "databases", "schemas", "tables"):
        if key not in scope or scope[key] is None:
            continue
        values = scope[key]
        if not isinstance(values, list):
            raise ValueError(f"Datasource grant scope.{key} must be a list of strings.")
        patterns = _normalized_scope_patterns(values, key)
        if patterns:
            normalized[key] = patterns
    return normalized


def _normalized_scope_patterns(values: list[Any], key: str) -> list[str]:
    if len(values) > 200:
        raise ValueError(f"Datasource grant scope.{key} cannot contain more than 200 patterns.")
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"Datasource grant scope.{key} must contain only strings.")
        candidate = value.strip()
        if candidate != value or not candidate or len(candidate) > 256:
            raise ValueError(f"Invalid datasource grant scope.{key} pattern.")
        normalized.add(candidate)
    return sorted(normalized)


def _grant_resource_id(subject_type: str, subject_id: str, datasource_key: str | None) -> str:
    suffix = f":{datasource_key}" if datasource_key is not None else ""
    return f"{subject_type}:{subject_id}{suffix}"


def _grant_validation_error_code(message: str) -> str:
    if "subject_type" in message:
        return "DATASOURCE_GRANT_SUBJECT_INVALID"
    if "_id" in message:
        return "DATASOURCE_GRANT_SUBJECT_INVALID"
    if "datasource_key" in message:
        return "DATASOURCE_GRANT_DATASOURCE_INVALID"
    if "effect" in message:
        return "DATASOURCE_GRANT_EFFECT_INVALID"
    return "DATASOURCE_GRANT_SCOPE_INVALID"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _datasource_error(error_code: str, message: str) -> Result[Any]:
    return Result(success=False, errorCode=error_code, errorMessage=message)

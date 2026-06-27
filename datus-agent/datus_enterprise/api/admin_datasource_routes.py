"""Enterprise datasource administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.configuration.project_config import ProjectOverride, load_project_override, save_project_override
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enterprise-datasources"])


AdminDatasourcesCtx = Annotated[AppContext, Depends(require_module("module.admin.datasources"))]


class SetDefaultDatasourceRequest(BaseModel):
    """Project-level datasource default mutation."""

    name: str


class AdminDatasourceSummary(BaseModel):
    """Sanitized datasource summary for admin selection UIs."""

    name: str
    type: str | None = None
    is_default: bool = False


class UpsertDatasourceGrantRequest(BaseModel):
    """Datasource grant metadata mutation."""

    effect: Any = "allow"
    scope: Any = Field(default_factory=dict)


class AdminDatasourceGrantSummary(BaseModel):
    """Sanitized datasource grant metadata."""

    subject_type: str
    subject_id: str
    datasource_key: str
    effect: str
    scope: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


@router.get(
    "/admin/datasources",
    response_model=Result[list[AdminDatasourceSummary]],
    summary="List Admin Datasources",
    description="Admin-only datasource key list. Connection details and secrets are never returned.",
)
async def list_admin_datasources_endpoint(
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
) -> Result[list[AdminDatasourceSummary]]:
    """Return sanitized configured datasource identifiers for admin workflows."""

    datasources = getattr(svc.agent_config.services, "datasources", {}) or {}
    default_datasource = _default_datasource_name(svc)
    items = [
        AdminDatasourceSummary(
            name=name,
            type=_datasource_type(config),
            is_default=name == default_datasource,
        )
        for name, config in sorted(datasources.items())
    ]
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=None,
            decision="allow",
            metadata={"operation": "list_admin_datasources", "count": len(items)},
        ),
    )
    return Result(success=True, data=items)


@router.get(
    "/admin/datasource-grants",
    response_model=Result[list[AdminDatasourceGrantSummary]],
    summary="List Datasource Grants",
)
async def list_admin_datasource_grants(
    ctx: AdminDatasourcesCtx,
    subject_type: Annotated[str | None, Query(description="Filter by subject type: user or role.")] = None,
    subject_id: Annotated[str | None, Query(description="Filter by subject id.")] = None,
    datasource_key: Annotated[str | None, Query(description="Filter by datasource key.")] = None,
) -> Result[list[AdminDatasourceGrantSummary]]:
    """Return role/user datasource grants for admin workflows."""

    invalid = _validate_optional_grant_filters(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="list_admin_datasource_grants",
            decision="deny",
            reason=invalid,
            metadata={"subject_type": subject_type, "subject_id": subject_id, "datasource_key": datasource_key},
        )
        return _datasource_error("DATASOURCE_GRANT_FILTER_INVALID", invalid)

    try:
        records = await deps.get_enterprise_extensions().datasource_grant_store.list_grants(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="list_admin_datasource_grants",
            decision="deny",
            reason="datasource grant list failed",
        )
        return _datasource_error("DATASOURCE_GRANT_LIST_FAILED", "Datasource grant list failed.")

    grants = [_grant_summary_from_record(record) for record in records]
    await _audit_datasource_grant(
        ctx,
        operation="list_admin_datasource_grants",
        decision="allow",
        metadata={
            "count": len(grants),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
        },
    )
    return Result(success=True, data=grants)


@router.get(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[AdminDatasourceGrantSummary],
    summary="Get Datasource Grant",
)
async def get_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    ctx: AdminDatasourcesCtx,
) -> Result[AdminDatasourceGrantSummary]:
    """Return one datasource grant record."""

    invalid = _validate_grant_identity(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_ID_INVALID", invalid)

    try:
        record = await deps.get_enterprise_extensions().datasource_grant_store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")
    if record is None:
        await _audit_datasource_grant(
            ctx,
            operation="get_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    summary = _grant_summary_from_record(record)
    await _audit_datasource_grant(
        ctx,
        operation="get_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[AdminDatasourceGrantSummary],
    summary="Upsert Datasource Grant",
)
async def upsert_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    body: UpsertDatasourceGrantRequest,
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
) -> Result[AdminDatasourceGrantSummary]:
    """Create or replace one role/user datasource grant."""

    invalid = (
        _validate_grant_identity(subject_type=subject_type, subject_id=subject_id, datasource_key=datasource_key)
        or _validate_grant_effect(body.effect)
        or _validate_grant_scope(body.scope)
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error(_grant_validation_error_code(invalid), invalid)

    if datasource_key not in (getattr(svc.agent_config.services, "datasources", {}) or {}):
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource not found",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_NOT_FOUND", "Datasource not found.")

    subject_error = await _validate_existing_grant_subject(
        ctx,
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    if subject_error is not None:
        return subject_error

    store = deps.get_enterprise_extensions().datasource_grant_store
    try:
        before = await store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")

    try:
        record = await store.put_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
            effect=_normalized_effect(body.effect),
            scope=_normalized_scope(body.scope),
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="upsert_admin_datasource_grant",
            decision="deny",
            reason="datasource grant upsert failed",
            resource_id=resource_id,
            old_summary=_grant_record_for_audit(before),
        )
        return _datasource_error("DATASOURCE_GRANT_UPSERT_FAILED", "Datasource grant upsert failed.")

    summary = _grant_summary_from_record(record)
    await _audit_datasource_grant(
        ctx,
        operation="upsert_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_record_for_audit(before),
        new_summary=_grant_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete(
    "/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    response_model=Result[dict],
    summary="Delete Datasource Grant",
)
async def delete_admin_datasource_grant(
    subject_type: str,
    subject_id: str,
    datasource_key: str,
    ctx: AdminDatasourcesCtx,
) -> Result[dict]:
    """Delete one datasource grant record."""

    invalid = _validate_grant_identity(
        subject_type=subject_type,
        subject_id=subject_id,
        datasource_key=datasource_key,
    )
    resource_id = _grant_resource_id(subject_type, subject_id, datasource_key)
    if invalid is not None:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason=invalid,
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().datasource_grant_store
    try:
        before = await store.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant read failed",
            resource_id=resource_id,
        )
        return _datasource_error("DATASOURCE_GRANT_READ_FAILED", "Datasource grant read failed.")
    if before is None:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    try:
        deleted = await store.delete_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
    except Exception:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant delete failed",
            resource_id=resource_id,
            old_summary=_grant_record_for_audit(before),
        )
        return _datasource_error("DATASOURCE_GRANT_DELETE_FAILED", "Datasource grant delete failed.")
    if not deleted:
        await _audit_datasource_grant(
            ctx,
            operation="delete_admin_datasource_grant",
            decision="deny",
            reason="datasource grant not found",
            resource_id=resource_id,
        )
        return _datasource_error("RESOURCE_NOT_FOUND", "Datasource grant not found.")

    await _audit_datasource_grant(
        ctx,
        operation="delete_admin_datasource_grant",
        decision="allow",
        resource_id=resource_id,
        old_summary=_grant_record_for_audit(before),
    )
    return Result(success=True, data={"deleted": True})


@router.put(
    "/admin/datasource-default",
    response_model=Result[dict],
    summary="Set Project Default Datasource",
    description="Admin-only project default datasource mutation. This is not a user request-level datasource switch.",
)
async def set_project_default_datasource_endpoint(
    body: SetDefaultDatasourceRequest,
    svc: ServiceDep,
    ctx: AdminDatasourcesCtx,
) -> Result[dict]:
    """Persist ``default_datasource`` to ``./.datus/config.yml``."""

    if body.name not in svc.agent_config.services.datasources:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.datasources",
                resource_type="datasource",
                resource_id=body.name,
                decision="deny",
                reason="datasource not found",
            ),
        )
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message=f"Datasource '{body.name}' not found in services.datasources.",
        )

    current = load_project_override() or ProjectOverride()
    current.default_datasource = body.name
    save_project_override(current)

    await _evict_current_project(ctx.project_id or "default")
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.datasources",
            resource_type="datasource",
            resource_id=body.name,
            decision="allow",
            metadata={"mutation": "set_project_default_datasource"},
        ),
    )

    return Result(success=True, data={"default_datasource": body.name, "scope": "project"})


async def _evict_current_project(project_id: str) -> None:
    try:
        await deps.evict_datus_service(project_id)
    except Exception:
        logger.exception(f"Failed to evict service cache for project {project_id}")


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
        normalized[key] = _normalized_scope_patterns(values, key)
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

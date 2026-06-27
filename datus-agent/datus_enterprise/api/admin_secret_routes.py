"""Enterprise secret reference administration routes."""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-secrets"])

AdminSecretsCtx = Annotated[AppContext, Depends(require_module("module.admin.secrets"))]

SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")
SECRET_PROVIDER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MAX_SECRET_NAME_LENGTH = 160
MAX_SECRET_PROVIDER_LENGTH = 80
MAX_SECRET_REFERENCE_LENGTH = 512
MAX_SECRET_DESCRIPTION_LENGTH = 300


class UpsertSecretRequest(BaseModel):
    """Enterprise secret reference mutation."""

    provider: Any
    reference: Any
    description: Any = Field(default=None)
    enabled: Any = True


class AdminSecretSummary(BaseModel):
    """Redaction-safe secret reference summary."""

    name: str
    provider: str
    ref_hint: str
    description: str | None = None
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/admin/secrets", response_model=Result[list[AdminSecretSummary]], summary="List Admin Secrets")
async def list_admin_secrets(
    ctx: AdminSecretsCtx,
    prefix: Annotated[str | None, Query(description="Filter by secret name prefix.")] = None,
) -> Result[list[AdminSecretSummary]]:
    """Return redaction-safe enterprise secret reference metadata."""

    invalid = _validate_optional_prefix(prefix)
    if invalid is not None:
        await _audit_secret(ctx, operation="list_admin_secrets", decision="deny", reason=invalid)
        return _secret_error("SECRET_FILTER_INVALID", invalid)

    store = deps.get_enterprise_extensions().secret_store
    if store is None:
        await _audit_secret(ctx, operation="list_admin_secrets", decision="deny", reason="secret store unavailable")
        return _secret_error("SECRET_STORE_UNAVAILABLE", "Secret store is not configured.")

    try:
        records = await store.list_secrets(prefix=prefix)
    except Exception:
        await _audit_secret(ctx, operation="list_admin_secrets", decision="deny", reason="secret list failed")
        return _secret_error("SECRET_LIST_FAILED", "Secret list failed.")

    secrets = [_secret_summary_from_record(record) for record in records]
    await _audit_secret(
        ctx,
        operation="list_admin_secrets",
        decision="allow",
        metadata={"count": len(secrets), "prefix": prefix},
    )
    return Result(success=True, data=secrets)


@router.get("/admin/secrets/{name:path}", response_model=Result[AdminSecretSummary], summary="Get Admin Secret")
async def get_admin_secret(name: str, ctx: AdminSecretsCtx) -> Result[AdminSecretSummary]:
    """Return one redaction-safe enterprise secret reference."""

    invalid = _validate_secret_name(name)
    if invalid is not None:
        await _audit_secret(ctx, operation="get_admin_secret", decision="deny", reason=invalid, resource_id=name)
        return _secret_error("SECRET_NAME_INVALID", invalid)

    store = deps.get_enterprise_extensions().secret_store
    if store is None:
        await _audit_secret(ctx, operation="get_admin_secret", decision="deny", reason="secret store unavailable")
        return _secret_error("SECRET_STORE_UNAVAILABLE", "Secret store is not configured.")

    try:
        record = await store.get_secret(name)
    except Exception:
        await _audit_secret(ctx, operation="get_admin_secret", decision="deny", reason="secret read failed")
        return _secret_error("SECRET_READ_FAILED", "Secret read failed.")
    if record is None:
        await _audit_secret(ctx, operation="get_admin_secret", decision="deny", reason="secret not found")
        return _secret_error("RESOURCE_NOT_FOUND", "Secret not found.")

    summary = _secret_summary_from_record(record)
    await _audit_secret(
        ctx,
        operation="get_admin_secret",
        decision="allow",
        resource_id=name,
        old_summary=_secret_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put("/admin/secrets/{name:path}", response_model=Result[AdminSecretSummary], summary="Upsert Admin Secret")
async def upsert_admin_secret(name: str, body: UpsertSecretRequest, ctx: AdminSecretsCtx) -> Result[AdminSecretSummary]:
    """Create or replace one enterprise secret reference without returning the raw reference."""

    normalized = _normalize_secret_request(name, body)
    if isinstance(normalized, str):
        await _audit_secret(ctx, operation="upsert_admin_secret", decision="deny", reason=normalized, resource_id=name)
        return _secret_error(_secret_validation_error_code(normalized), normalized)

    store = deps.get_enterprise_extensions().secret_store
    if store is None:
        await _audit_secret(ctx, operation="upsert_admin_secret", decision="deny", reason="secret store unavailable")
        return _secret_error("SECRET_STORE_UNAVAILABLE", "Secret store is not configured.")

    old_summary = None
    try:
        before = await store.get_secret(normalized["name"])
        if before is not None:
            old_summary = _secret_summary_for_audit(_secret_summary_from_record(before))
        record = await store.put_secret(**normalized)
    except Exception:
        await _audit_secret(
            ctx,
            operation="upsert_admin_secret",
            decision="deny",
            reason="secret upsert failed",
            resource_id=normalized["name"],
            old_summary=old_summary,
        )
        return _secret_error("SECRET_UPSERT_FAILED", "Secret upsert failed.")

    summary = _secret_summary_from_record(record)
    await _audit_secret(
        ctx,
        operation="upsert_admin_secret",
        decision="allow",
        resource_id=normalized["name"],
        old_summary=old_summary,
        new_summary=_secret_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete("/admin/secrets/{name:path}", response_model=Result[dict], summary="Delete Admin Secret")
async def delete_admin_secret(name: str, ctx: AdminSecretsCtx) -> Result[dict]:
    """Delete one enterprise secret reference."""

    invalid = _validate_secret_name(name)
    if invalid is not None:
        await _audit_secret(ctx, operation="delete_admin_secret", decision="deny", reason=invalid, resource_id=name)
        return _secret_error("SECRET_NAME_INVALID", invalid)

    store = deps.get_enterprise_extensions().secret_store
    if store is None:
        await _audit_secret(ctx, operation="delete_admin_secret", decision="deny", reason="secret store unavailable")
        return _secret_error("SECRET_STORE_UNAVAILABLE", "Secret store is not configured.")

    try:
        before = await store.get_secret(name)
    except Exception:
        await _audit_secret(ctx, operation="delete_admin_secret", decision="deny", reason="secret read failed")
        return _secret_error("SECRET_READ_FAILED", "Secret read failed.")
    if before is None:
        await _audit_secret(ctx, operation="delete_admin_secret", decision="deny", reason="secret not found")
        return _secret_error("RESOURCE_NOT_FOUND", "Secret not found.")

    try:
        deleted = await store.delete_secret(name)
    except Exception:
        await _audit_secret(
            ctx,
            operation="delete_admin_secret",
            decision="deny",
            reason="secret delete failed",
            resource_id=name,
            old_summary=_secret_summary_for_audit(_secret_summary_from_record(before)),
        )
        return _secret_error("SECRET_DELETE_FAILED", "Secret delete failed.")
    if not deleted:
        await _audit_secret(ctx, operation="delete_admin_secret", decision="deny", reason="secret not found")
        return _secret_error("RESOURCE_NOT_FOUND", "Secret not found.")

    await _audit_secret(
        ctx,
        operation="delete_admin_secret",
        decision="allow",
        resource_id=name,
        old_summary=_secret_summary_for_audit(_secret_summary_from_record(before)),
    )
    return Result(success=True, data={"deleted": True})


def _normalize_secret_request(name: str, body: UpsertSecretRequest) -> dict[str, Any] | str:
    invalid = _validate_secret_name(name)
    if invalid is not None:
        return invalid
    provider = _normalize_provider(body.provider)
    if provider is None:
        return "Secret provider is invalid."
    reference = _normalize_reference(body.reference)
    if reference is None:
        return "Secret reference is invalid."
    description = _normalize_description(body.description)
    if description is False:
        return "Secret description is invalid."
    if not isinstance(body.enabled, bool):
        return "Secret enabled must be a boolean."
    return {
        "name": name,
        "provider": provider,
        "reference": reference,
        "description": description,
        "enabled": body.enabled,
    }


def _validate_optional_prefix(prefix: str | None) -> str | None:
    if prefix is None:
        return None
    return _validate_secret_name(prefix)


def _validate_secret_name(name: str) -> str | None:
    if not isinstance(name, str):
        return "Secret name is invalid."
    candidate = name.strip()
    if (
        candidate != name
        or not candidate
        or len(candidate) > MAX_SECRET_NAME_LENGTH
        or not SECRET_NAME_RE.fullmatch(candidate)
    ):
        return "Secret name is invalid."
    return None


def _normalize_provider(provider: Any) -> str | None:
    if not isinstance(provider, str):
        return None
    candidate = provider.strip()
    if (
        candidate != provider
        or not candidate
        or len(candidate) > MAX_SECRET_PROVIDER_LENGTH
        or not SECRET_PROVIDER_RE.fullmatch(candidate)
    ):
        return None
    return candidate


def _normalize_reference(reference: Any) -> str | None:
    if not isinstance(reference, str):
        return None
    candidate = reference.strip()
    if candidate != reference or not candidate or len(candidate) > MAX_SECRET_REFERENCE_LENGTH:
        return None
    return candidate


def _normalize_description(description: Any) -> str | None | bool:
    if description is None:
        return None
    if not isinstance(description, str):
        return False
    candidate = description.strip()
    if candidate != description or len(candidate) > MAX_SECRET_DESCRIPTION_LENGTH:
        return False
    return candidate or None


def _secret_summary_from_record(record: dict[str, Any]) -> AdminSecretSummary:
    return AdminSecretSummary(
        name=str(record.get("name") or ""),
        provider=str(record.get("provider") or ""),
        ref_hint=_redact_reference(record.get("reference")),
        description=_optional_str(record.get("description")),
        enabled=bool(record.get("enabled")),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _secret_summary_for_audit(summary: AdminSecretSummary) -> dict[str, Any]:
    return {
        "name": summary.name,
        "provider": summary.provider,
        "ref_hint": summary.ref_hint,
        "enabled": summary.enabled,
    }


def _redact_reference(reference: Any) -> str:
    raw = str(reference or "")
    if len(raw) <= 4:
        return "***"
    return f"***{raw[-4:]}"


async def _audit_secret(
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
    event_metadata = {"operation": operation}
    if metadata:
        event_metadata.update(metadata)
    if old_summary is not None:
        event_metadata["old_summary"] = old_summary
    if new_summary is not None:
        event_metadata["new_summary"] = new_summary
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.secrets",
            resource_type="secret",
            resource_id=resource_id,
            decision=decision,
            reason=reason,
            metadata=event_metadata,
        ),
    )


def _secret_error(code: str, message: str) -> Result:
    return Result(success=False, errorCode=code, errorMessage=message)


def _secret_validation_error_code(message: str) -> str:
    if "name" in message:
        return "SECRET_NAME_INVALID"
    if "provider" in message:
        return "SECRET_PROVIDER_INVALID"
    if "reference" in message:
        return "SECRET_REFERENCE_INVALID"
    if "description" in message:
        return "SECRET_DESCRIPTION_INVALID"
    if "enabled" in message:
        return "SECRET_ENABLED_INVALID"
    return "SECRET_INVALID"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None

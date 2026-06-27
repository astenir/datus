"""Enterprise quota enforcement helpers."""

from __future__ import annotations

from typing import Any

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision


async def consume_enterprise_quota(
    ctx: AppContext,
    *,
    resource: str,
    amount: int = 1,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Result | None:
    """Consume quota for the current enterprise principal, returning an error result when denied."""

    extensions = deps.get_enterprise_extensions()
    if not extensions.enabled:
        return None

    store = extensions.quota_store
    audit_metadata = {"quota_resource": resource, "amount": amount}
    if metadata:
        audit_metadata.update(metadata)

    if store is None:
        await _audit_quota(
            ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            decision="deny",
            reason="quota store unavailable",
            metadata=audit_metadata,
        )
        return _quota_error("QUOTA_STORE_UNAVAILABLE", "Quota store is not configured.")

    subjects = _quota_subjects(ctx)
    try:
        decision = await store.consume_quota(subjects=subjects, resource=resource, amount=amount)
    except Exception:
        await _audit_quota(
            ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            decision="deny",
            reason="quota check failed",
            metadata=audit_metadata,
        )
        return _quota_error("QUOTA_CHECK_FAILED", "Quota check failed.")

    if bool(decision.get("allowed", True)):
        await _audit_quota(
            ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            decision="allow",
            reason=None,
            metadata={**audit_metadata, "subjects": subjects, "usage_count": len(decision.get("usage") or [])},
        )
        return None

    safe_decision = _quota_decision_summary(decision)
    await _audit_quota(
        ctx,
        resource_type=resource_type,
        resource_id=resource_id,
        decision="deny",
        reason="quota exceeded",
        metadata={**audit_metadata, **safe_decision},
    )
    return _quota_error("QUOTA_EXCEEDED", "Quota exceeded.")


def _quota_subjects(ctx: AppContext) -> list[dict[str, str]]:
    subjects: list[dict[str, str]] = []
    if ctx.user_id:
        subjects.append({"subject_type": "user", "subject_id": ctx.user_id})
    for role in _context_roles(ctx):
        subjects.append({"subject_type": "role", "subject_id": role})
    subjects.append({"subject_type": "global", "subject_id": "*"})
    return subjects


def _context_roles(ctx: AppContext) -> list[str]:
    roles = set(_string_values(getattr(ctx, "roles", None)))
    principal = getattr(ctx, "principal", None) or {}
    roles.update(_string_values(principal.get("roles")))
    return sorted(roles)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    return [str(item).strip() for item in values if str(item).strip()]


def _quota_decision_summary(decision: dict[str, Any]) -> dict[str, Any]:
    keys = ("subject_type", "subject_id", "resource", "limit", "used", "remaining", "window_start", "window_seconds")
    return {key: decision[key] for key in keys if key in decision}


async def _audit_quota(
    ctx: AppContext,
    *,
    resource_type: str,
    resource_id: str | None,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any],
) -> None:
    await audit_decision(
        ctx,
        AuditEvent(
            action="quota.consume",
            resource_type=resource_type,
            resource_id=resource_id,
            decision=decision,
            reason=reason,
            metadata=metadata,
        ),
    )


def _quota_error(code: str, message: str) -> Result:
    return Result(success=False, errorCode=code, errorMessage=message)

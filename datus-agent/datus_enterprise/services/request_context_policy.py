"""Enterprise request-context validation and authorization projection."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import AuditEvent
from datus.utils.datasource_scope import SCOPE_CONSTRAINTS_KEY, grant_may_use_tree_scope

MetadataCall = Callable[..., Awaitable[Any]]
AuditWriter = Callable[[EnterpriseExtensions, AuditEvent], Awaitable[None]]
_SCOPE_GLOB_META_CHARS = "*?["


async def validate_enterprise_context(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    metadata_call: MetadataCall,
    write_audit: AuditWriter,
) -> None:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    try:
        user = await metadata_call(
            enterprise_extensions.user_store.get_user(ctx.user_id),
            operation="user_store.get_user",
        )
    except Exception as e:
        await write_audit(
            enterprise_extensions,
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user status unavailable",
            ),
        )
        raise HTTPException(status_code=403, detail="USER_STATUS_UNAVAILABLE") from e
    if user is not None and not bool(user.get("enabled", True)):
        await write_audit(
            enterprise_extensions,
            AuditEvent(
                user_id=ctx.user_id,
                action="auth.enterprise_user_status",
                resource_type="user",
                resource_id=ctx.user_id,
                decision="deny",
                reason="user disabled",
            ),
        )
        raise HTTPException(status_code=403, detail="USER_DISABLED")
    if user is None and enterprise_extensions.user_auto_provisioning.enabled:
        await _auto_provision_enterprise_user(
            ctx,
            enterprise_extensions,
            metadata_call=metadata_call,
            write_audit=write_audit,
        )


async def refresh_enterprise_context(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    metadata_call: MetadataCall,
    write_audit: AuditWriter,
) -> None:
    """Merge request RBAC and datasource grants from enterprise metadata stores."""

    is_dev_admin = _is_dev_admin_context(ctx)
    provider_roles = list(ctx.roles or [])
    provider_permissions = set(ctx.permissions or set())
    provider_datasource_grants = copy.deepcopy(ctx.datasource_grants or {})

    try:
        stored_role_ids = await metadata_call(
            enterprise_extensions.role_store.list_user_roles(ctx.user_id or ""),
            operation="role_store.list_user_roles",
        )
        role_ids = _merge_string_lists(stored_role_ids)
        role_permissions: set[str] = set()
        roles = await asyncio.gather(
            *(
                metadata_call(
                    enterprise_extensions.role_store.get_role(role_id),
                    operation=f"role_store.get_role.{role_id}",
                )
                for role_id in role_ids
            )
        )
        for role_id, role in zip(role_ids, roles):
            if role is None:
                await _audit_enterprise_context_deny(
                    ctx,
                    enterprise_extensions,
                    write_audit=write_audit,
                    reason="role metadata missing",
                    metadata={"role_id": role_id},
                )
                raise HTTPException(status_code=403, detail="ROLE_CONTEXT_UNAVAILABLE")
            if isinstance(role, dict):
                role_permissions.update(_string_set(role.get("permissions")))
    except HTTPException:
        raise
    except Exception as e:
        await _audit_enterprise_context_deny(
            ctx,
            enterprise_extensions,
            write_audit=write_audit,
            reason="role context unavailable",
        )
        raise HTTPException(status_code=403, detail="ROLE_CONTEXT_UNAVAILABLE") from e

    try:
        datasource_grants = await _merged_datasource_grants(
            ctx,
            role_ids,
            enterprise_extensions,
            metadata_call=metadata_call,
        )
    except Exception as e:
        await _audit_enterprise_context_deny(
            ctx,
            enterprise_extensions,
            write_audit=write_audit,
            reason="datasource grants unavailable",
        )
        raise HTTPException(status_code=403, detail="DATASOURCE_GRANTS_UNAVAILABLE") from e

    if is_dev_admin:
        role_ids = _merge_string_lists(role_ids + provider_roles)
        role_permissions.update(provider_permissions)
        datasource_grants = _merge_provider_datasource_grants(datasource_grants, provider_datasource_grants)

    ctx.roles = role_ids
    ctx.permissions = role_permissions
    ctx.datasource_grants = datasource_grants
    ctx.is_admin = _matches_admin_context(ctx.roles, ctx.permissions)
    ctx.principal = dict(ctx.principal or {})
    ctx.principal["roles"] = list(ctx.roles)
    ctx.principal["permissions"] = sorted(ctx.permissions)
    ctx.principal["datasource_grants"] = copy.deepcopy(ctx.datasource_grants)


async def _merged_datasource_grants(
    ctx: AppContext,
    role_ids: list[str],
    enterprise_extensions: EnterpriseExtensions,
    *,
    metadata_call: MetadataCall,
) -> dict[str, Any]:
    grants: dict[str, Any] = {}
    subjects = [("role", role_id) for role_id in role_ids]
    subjects.append(("user", ctx.user_id or ""))
    record_batches = await asyncio.gather(
        *(
            metadata_call(
                enterprise_extensions.datasource_grant_store.list_grants(
                    subject_type=subject_type,
                    subject_id=subject_id,
                ),
                operation=f"datasource_grant_store.list_grants.{subject_type}.{subject_id}",
            )
            for subject_type, subject_id in subjects
        )
    )

    for (subject_type, _subject_id), records in zip(subjects, record_batches):
        mode = "union" if subject_type == "role" else "narrow"
        for record in records:
            _merge_grant_record(grants, record, mode=mode)
    return grants


async def _auto_provision_enterprise_user(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    metadata_call: MetadataCall,
    write_audit: AuditWriter,
) -> None:
    """Create a least-privilege enterprise user record on first successful auth."""

    role_ids = list(enterprise_extensions.user_auto_provisioning.default_role_ids)
    for role_id in role_ids:
        try:
            role = await metadata_call(
                enterprise_extensions.role_store.get_role(role_id),
                operation="role_store.get_role.default",
            )
        except Exception as e:
            await _audit_auto_provision(
                ctx,
                enterprise_extensions,
                write_audit=write_audit,
                decision="deny",
                reason="default role unavailable",
                metadata={"role_id": role_id},
            )
            raise HTTPException(status_code=403, detail="USER_AUTO_PROVISION_UNAVAILABLE") from e
        if role is None:
            await _audit_auto_provision(
                ctx,
                enterprise_extensions,
                write_audit=write_audit,
                decision="deny",
                reason="default role not found",
                metadata={"role_id": role_id},
            )
            raise HTTPException(status_code=403, detail="USER_AUTO_PROVISION_ROLE_NOT_FOUND")

    try:
        await metadata_call(
            enterprise_extensions.user_store.upsert_user(
                user_id=ctx.user_id or "",
                display_name=_principal_str(ctx, "display_name") or _principal_str(ctx, "realname") or ctx.user_id,
                email=_principal_str(ctx, "email"),
                enabled=True,
                external_user_id=_principal_str(ctx, "external_user_id") or _principal_str(ctx, "userId"),
                department=_principal_str(ctx, "department"),
                title=_principal_str(ctx, "title"),
                last_seen_at=datetime.now(timezone.utc).isoformat(),
            ),
            operation="user_store.upsert_user",
        )
        if role_ids:
            await metadata_call(
                enterprise_extensions.role_store.set_user_roles(ctx.user_id or "", role_ids),
                operation="role_store.set_user_roles",
            )
    except Exception as e:
        await _audit_auto_provision(
            ctx,
            enterprise_extensions,
            write_audit=write_audit,
            decision="deny",
            reason="user auto-provision failed",
            metadata={"default_role_ids": role_ids},
        )
        raise HTTPException(status_code=403, detail="USER_AUTO_PROVISION_UNAVAILABLE") from e

    await _audit_auto_provision(
        ctx,
        enterprise_extensions,
        write_audit=write_audit,
        decision="allow",
        reason="user auto-provisioned",
        metadata={"default_role_ids": role_ids},
    )


async def _audit_auto_provision(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    write_audit: AuditWriter,
    decision: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    await write_audit(
        enterprise_extensions,
        AuditEvent(
            user_id=ctx.user_id,
            action="auth.enterprise_user_auto_provision",
            resource_type="user",
            resource_id=ctx.user_id,
            decision=decision,
            reason=reason,
            metadata=metadata or {},
        ),
    )


def _principal_str(ctx: AppContext, key: str) -> str | None:
    value = (ctx.principal or {}).get(key)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _merge_grant_record(grants: dict[str, Any], record: dict[str, Any], *, mode: str = "union") -> None:
    datasource_key = str(record.get("datasource_key") or "").strip()
    if not datasource_key:
        return
    merged = dict(record.get("scope") or {})
    effect = str(record.get("effect") or "allow").strip().lower()
    merged["effect"] = effect
    existing = grants.get(datasource_key)
    if _grant_effect(existing) == "deny" or effect == "deny":
        grants[datasource_key] = {"effect": "deny"}
        return
    if not isinstance(existing, dict):
        grants[datasource_key] = merged
        return
    if mode == "narrow":
        grants[datasource_key] = _intersect_allow_grants(existing, merged)
        return
    grants[datasource_key] = _union_allow_grants(existing, merged)


def _merge_provider_datasource_grants(grants: dict[str, Any], provider_grants: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(grants)
    for datasource_key, grant in (provider_grants or {}).items():
        key = str(datasource_key or "").strip()
        if not key:
            continue
        if _grant_effect(grant) == "deny":
            merged[key] = {"effect": "deny"}
            continue
        if grant is True:
            provider_grant = {"effect": "allow"}
        elif isinstance(grant, dict):
            provider_grant = copy.deepcopy(grant)
            provider_grant.setdefault("effect", "allow")
        else:
            continue
        existing = merged.get(key)
        if isinstance(existing, dict):
            merged[key] = _union_allow_grants(existing, provider_grant)
        else:
            merged[key] = provider_grant
    return merged


def _union_allow_grants(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = {"effect": "allow"}
    for key in ("allow_catalog", "allow_sql"):
        merged[key] = _grant_bool_allows(left, key) or _grant_bool_allows(right, key)
    for key in ("catalogs", "databases", "schemas", "tables"):
        patterns = _union_scope_patterns(left.get(key), right.get(key))
        if patterns is not None:
            merged[key] = patterns
    return merged


def _intersect_allow_grants(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = {"effect": "allow"}
    for key in ("allow_catalog", "allow_sql"):
        merged[key] = _grant_bool_allows(left, key) and _grant_bool_allows(right, key)
    for key in ("catalogs", "databases", "schemas", "tables"):
        patterns = _intersect_scope_patterns(left.get(key), right.get(key))
        if patterns is not None:
            merged[key] = patterns
    if grant_may_use_tree_scope(left) or grant_may_use_tree_scope(right):
        merged[SCOPE_CONSTRAINTS_KEY] = [copy.deepcopy(left), copy.deepcopy(right)]
    return merged


def _grant_bool_allows(grant: dict[str, Any], key: str) -> bool:
    return grant.get(key) is not False


def _union_scope_patterns(left: Any, right: Any) -> list[str] | None:
    left_patterns = _scope_pattern_list(left)
    right_patterns = _scope_pattern_list(right)
    if left_patterns is None:
        return right_patterns
    if right_patterns is None:
        return left_patterns
    return sorted({*left_patterns, *right_patterns})


def _intersect_scope_patterns(left: Any, right: Any) -> list[str] | None:
    left_patterns = _scope_pattern_list(left)
    right_patterns = _scope_pattern_list(right)
    if left_patterns is None:
        return right_patterns
    if right_patterns is None:
        return left_patterns
    intersected: set[str] = set()
    for left_pattern in left_patterns:
        for right_pattern in right_patterns:
            narrower = _narrower_scope_pattern(left_pattern, right_pattern)
            if narrower is not None:
                intersected.add(narrower)
    return sorted(intersected)


def _narrower_scope_pattern(left_pattern: str, right_pattern: str) -> str | None:
    if _scope_pattern_includes(left_pattern, right_pattern):
        return right_pattern
    if _scope_pattern_includes(right_pattern, left_pattern):
        return left_pattern
    return None


def _scope_pattern_includes(container: str, candidate: str) -> bool:
    if container == candidate or container == "*":
        return True
    if not _has_scope_glob(candidate):
        return fnmatchcase(candidate, container)

    container_prefix = _simple_prefix_glob(container)
    if container_prefix is None:
        return False
    return _literal_glob_prefix(candidate).startswith(container_prefix)


def _has_scope_glob(pattern: str) -> bool:
    return any(char in pattern for char in _SCOPE_GLOB_META_CHARS)


def _simple_prefix_glob(pattern: str) -> str | None:
    if not pattern.endswith("*"):
        return None
    prefix = pattern[:-1]
    if _has_scope_glob(prefix):
        return None
    return prefix


def _literal_glob_prefix(pattern: str) -> str:
    for index, char in enumerate(pattern):
        if char in _SCOPE_GLOB_META_CHARS:
            return pattern[:index]
    return pattern


def _scope_pattern_list(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _grant_effect(grant: Any) -> str | None:
    if grant is True:
        return "allow"
    if grant is False:
        return "deny"
    if isinstance(grant, dict):
        return str(grant.get("effect") or "allow").strip().lower()
    return None


def _merge_string_lists(values: list[Any]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _string_set(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item.strip() for item in raw if isinstance(item, str) and item.strip()}
    return set()


def _is_dev_admin_context(ctx: AppContext) -> bool:
    return bool((ctx.principal or {}).get("_datus_dev_admin") is True)


def _matches_admin_context(roles: list[str], permissions: set[str]) -> bool:
    return (
        "enterprise_admin" in roles
        or "*" in permissions
        or "module.admin.*" in permissions
        or "module.*" in permissions
    )


async def _audit_enterprise_context_deny(
    ctx: AppContext,
    enterprise_extensions: EnterpriseExtensions,
    *,
    write_audit: AuditWriter,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    await write_audit(
        enterprise_extensions,
        AuditEvent(
            user_id=ctx.user_id,
            action="auth.enterprise_context",
            resource_type="user",
            resource_id=ctx.user_id,
            decision="deny",
            reason=reason,
            metadata=metadata or {},
        ),
    )

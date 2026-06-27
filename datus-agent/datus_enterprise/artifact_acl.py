"""Artifact ACL helpers for enterprise report/dashboard routes."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable, List, Sequence, TypeVar

from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import get_artifact_acl_store
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import ResourceRef, authorize

TManifest = TypeVar("TManifest", bound=ArtifactManifest)


async def filter_visible_artifacts(
    ctx: AppContext,
    *,
    artifact_type: str,
    manifests: Sequence[TManifest],
) -> List[TManifest]:
    """Filter manifests through the local-compatible ACL hook."""

    store = get_artifact_acl_store()
    if store is not None:
        visible: list[TManifest] = []
        for manifest in manifests:
            if await _store_acl_allows(store, ctx, artifact_type=artifact_type, slug=manifest.slug):
                visible.append(manifest)
        return visible

    allowed_slugs = _allowed_slugs(ctx, artifact_type)
    if allowed_slugs is None:
        return list(manifests)
    return [manifest for manifest in manifests if manifest.slug in allowed_slugs]


async def require_artifact_access(ctx: AppContext, *, artifact_type: str, slug: str, action: str) -> None:
    """Authorize one artifact slug.

    The default local ACL reads an optional ``principal.artifact_acl`` map for
    test/dev mode. Missing ACL data means local-compatible allow.
    """

    permission_action = f"module.{artifact_type}.{action}"
    decision = await authorize(ctx, action=permission_action, resource=ResourceRef(type=artifact_type, id=slug))
    if not decision.allowed:
        await audit_decision(
            ctx,
            AuditEvent(
                action=permission_action,
                resource_type=artifact_type,
                resource_id=slug,
                decision="deny",
                reason=decision.reason,
            ),
        )
        raise HTTPException(status_code=403, detail=decision.reason or "Permission denied.")

    store = get_artifact_acl_store()
    if store is not None:
        if not await _store_acl_allows(store, ctx, artifact_type=artifact_type, slug=slug):
            await audit_decision(
                ctx,
                AuditEvent(
                    action=permission_action,
                    resource_type=artifact_type,
                    resource_id=slug,
                    decision="deny",
                    reason="artifact ACL denied",
                ),
            )
            raise HTTPException(status_code=404, detail="Artifact not found.")

        await audit_decision(
            ctx,
            AuditEvent(action=permission_action, resource_type=artifact_type, resource_id=slug, decision="allow"),
        )
        return

    allowed_slugs = _allowed_slugs(ctx, artifact_type)
    if allowed_slugs is not None and slug not in allowed_slugs:
        await audit_decision(
            ctx,
            AuditEvent(
                action=permission_action,
                resource_type=artifact_type,
                resource_id=slug,
                decision="deny",
                reason="artifact ACL denied",
            ),
        )
        raise HTTPException(status_code=404, detail="Artifact not found.")

    await audit_decision(
        ctx,
        AuditEvent(action=permission_action, resource_type=artifact_type, resource_id=slug, decision="allow"),
    )


async def _store_acl_allows(store: Any, ctx: AppContext, *, artifact_type: str, slug: str) -> bool:
    try:
        raw_acl = await store.get_acl(artifact_type=artifact_type, slug=slug)
    except Exception:
        return False
    return _acl_allows(ctx, raw_acl)


def _acl_allows(ctx: AppContext, raw_acl: Any) -> bool:
    if not isinstance(raw_acl, dict):
        return False

    owner_user_id = raw_acl.get("owner_user_id")
    if owner_user_id and ctx.user_id == str(owner_user_id):
        return True
    if ctx.is_admin or _has_permission(ctx, "module.admin.artifacts"):
        return True

    visibility = raw_acl.get("visibility")
    if visibility == "enterprise":
        return True
    if visibility == "role":
        allowed_roles = _string_set(raw_acl.get("allowed_roles"))
        return bool(allowed_roles.intersection(ctx.roles))
    return False


def _has_permission(ctx: AppContext, permission_key: str) -> bool:
    if ctx.permissions:
        return _matches_permission(permission_key, ctx.permissions)
    principal_permissions = ctx.principal.get("permissions")
    return _matches_permission(permission_key, _string_set(principal_permissions))


def _matches_permission(permission_key: str, permissions: Iterable[str]) -> bool:
    return any(permission == "*" or fnmatchcase(permission_key, permission) for permission in permissions)


def _string_set(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Iterable):
        return {item for item in raw if isinstance(item, str)}
    return set()


def _allowed_slugs(ctx: AppContext, artifact_type: str) -> set[str] | None:
    raw_acl = ctx.principal.get("artifact_acl")
    if not isinstance(raw_acl, dict):
        return None
    raw_slugs = raw_acl.get(artifact_type)
    if raw_slugs is None:
        return None
    if isinstance(raw_slugs, str):
        return {raw_slugs}
    if isinstance(raw_slugs, Iterable):
        return {slug for slug in raw_slugs if isinstance(slug, str)}
    return set()

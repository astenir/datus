"""Artifact ACL helpers for enterprise report/dashboard routes."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable, List, Sequence, TypeVar

from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import get_artifact_acl_store
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import ResourceRef, authorize

TManifest = TypeVar("TManifest", bound=ArtifactManifest)

DEFAULT_ARTIFACT_ACL_VISIBILITY = "private"
logger = get_logger(__name__)


def build_default_private_acl(*, owner_user_id: str, datasources: Sequence[str] | None = None) -> dict[str, Any]:
    """Return the default ACL for a newly-created report/dashboard artifact."""

    return {
        "owner_user_id": owner_user_id,
        "visibility": DEFAULT_ARTIFACT_ACL_VISIBILITY,
        "allowed_roles": [],
        "allowed_user_ids": [],
        "datasources": _normalized_strings(datasources or []),
    }


async def ensure_default_private_acl(
    store: Any,
    *,
    artifact_type: str,
    slug: str,
    owner_user_id: str | None,
    datasources: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    """Create a default private ACL when the artifact has no stored ACL yet."""

    owner = str(owner_user_id or "").strip()
    if store is None or not owner:
        return None
    try:
        return await store.get_acl(artifact_type=artifact_type, slug=slug)
    except KeyError:
        default_acl = build_default_private_acl(owner_user_id=owner, datasources=datasources)
        return await store.put_acl(artifact_type=artifact_type, slug=slug, acl=default_acl)


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
        await _audit_artifact_access(
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
            await _audit_artifact_access(
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

        await _audit_artifact_access(
            ctx,
            AuditEvent(action=permission_action, resource_type=artifact_type, resource_id=slug, decision="allow"),
        )
        return

    allowed_slugs = _allowed_slugs(ctx, artifact_type)
    if allowed_slugs is not None and slug not in allowed_slugs:
        await _audit_artifact_access(
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

    await _audit_artifact_access(
        ctx,
        AuditEvent(action=permission_action, resource_type=artifact_type, resource_id=slug, decision="allow"),
    )


async def _audit_artifact_access(ctx: AppContext, event: AuditEvent) -> None:
    try:
        await audit_decision(ctx, event)
    except Exception:
        logger.warning(
            "Artifact access audit failed for action=%s resource_type=%s decision=%s",
            event.action,
            event.resource_type,
            event.decision,
            exc_info=True,
        )


async def _store_acl_allows(store: Any, ctx: AppContext, *, artifact_type: str, slug: str) -> bool:
    try:
        raw_acl = await store.get_acl(artifact_type=artifact_type, slug=slug)
    except Exception:
        return False
    return await _acl_allows(ctx, raw_acl)


async def _acl_allows(ctx: AppContext, raw_acl: Any) -> bool:
    if not isinstance(raw_acl, dict):
        return False

    owner_user_id = raw_acl.get("owner_user_id")
    if owner_user_id and ctx.user_id == str(owner_user_id):
        return True
    if await _is_authorized(ctx, "module.admin.artifacts", resource_type="artifact_acl"):
        return True
    allowed_user_ids = _string_set(raw_acl.get("allowed_user_ids"))
    if ctx.user_id and ctx.user_id in allowed_user_ids:
        return True

    visibility = raw_acl.get("visibility")
    if visibility == "enterprise":
        return True
    if visibility == "role":
        allowed_roles = _string_set(raw_acl.get("allowed_roles"))
        return bool(allowed_roles.intersection(ctx.roles))
    return False


async def _is_authorized(ctx: AppContext, permission_key: str, *, resource_type: str) -> bool:
    decision = await authorize(ctx, action=permission_key, resource=ResourceRef(type=resource_type, id=permission_key))
    return decision.allowed


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


def _normalized_strings(raw: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


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

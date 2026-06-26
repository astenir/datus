"""Artifact ACL helpers for enterprise report/dashboard routes."""

from __future__ import annotations

from typing import Iterable, List, Sequence, TypeVar

from fastapi import HTTPException

from datus.api.auth.context import AppContext
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

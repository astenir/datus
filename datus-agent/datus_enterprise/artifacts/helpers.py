"""Shared non-route helpers for enterprise Artifact APIs."""

from __future__ import annotations

from inspect import isawaitable
from pathlib import Path
from typing import Any, List, Literal

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import get_artifact_acl_store
from datus.api.models.base_models import Result
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.utils.loggings import get_logger
from datus_enterprise.artifacts.acl import (
    require_artifact_access,
)
from datus_enterprise.artifacts.models import (
    AdminArtifactSummary,
    ArtifactAcl,
    ArtifactListItem,
    ArtifactShare,
    ArtifactShareRoleSummary,
    ArtifactShareUpdate,
    ArtifactShareUserSummary,
    ShareArtifactType,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import ResourceRef, authorize

logger = get_logger(__name__)


def _project_files_root(svc: ServiceDep) -> Path:
    return Path(svc.agent_config.project_root)


def _admin_artifact_matches_search(item: AdminArtifactSummary, search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    manifest = item.manifest
    values = (
        item.artifact_type,
        manifest.slug,
        manifest.name,
        manifest.description,
        *(manifest.datasources or []),
    )
    return any(query in str(value or "").casefold() for value in values)


async def _resolve_request_service(request: Request) -> ServiceDep:
    service_provider = request.app.dependency_overrides.get(deps.get_datus_service, deps.get_datus_service)
    result = service_provider(request)
    if isawaitable(result):
        return await result
    return result


async def _get_creator_artifact_share(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
) -> Result[ArtifactShare]:
    artifact = await _find_artifact(svc, artifact_type=artifact_type, slug=slug)
    if artifact is None:
        await _audit_artifact_share(
            ctx,
            operation="get_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact not found",
        )
        return _artifact_not_found()

    loaded = await _load_artifact_acl_for_share(ctx, artifact_type=artifact_type, slug=slug, operation="get")
    if isinstance(loaded, Result):
        return loaded
    acl = loaded
    if not await _can_manage_artifact_share(ctx, acl):
        await _audit_artifact_share(
            ctx,
            operation="get_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact owner required",
        )
        return Result(success=False, errorCode="ARTIFACT_FORBIDDEN", errorMessage="Artifact not found.")

    await _audit_artifact_share(
        ctx,
        operation="get_artifact_share",
        artifact_type=artifact_type,
        slug=slug,
        decision="allow",
        reason=None,
    )
    return Result(success=True, data=_share_from_acl(acl))


async def _put_creator_artifact_share(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
    share: ArtifactShareUpdate,
) -> Result[ArtifactShare]:
    artifact = await _find_artifact(svc, artifact_type=artifact_type, slug=slug)
    if artifact is None:
        await _audit_artifact_share(
            ctx,
            operation="put_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact not found",
        )
        return _artifact_not_found()

    loaded = await _load_artifact_acl_for_share(ctx, artifact_type=artifact_type, slug=slug, operation="put")
    if isinstance(loaded, Result):
        return loaded
    acl = loaded
    if not await _can_manage_artifact_share(ctx, acl):
        await _audit_artifact_share(
            ctx,
            operation="put_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact owner required",
        )
        return Result(success=False, errorCode="ARTIFACT_FORBIDDEN", errorMessage="Artifact not found.")

    store = get_artifact_acl_store()
    if store is None:
        return _artifact_acl_unavailable()
    old_acl = acl.model_dump()
    updated_acl = ArtifactAcl(
        owner_user_id=acl.owner_user_id,
        visibility=share.visibility,
        allowed_roles=_normalized_list(share.allowed_roles),
        allowed_user_ids=_normalized_list(share.allowed_user_ids),
        datasources=acl.datasources,
    )
    try:
        stored_acl = await store.put_acl(artifact_type=artifact_type, slug=slug, acl=updated_acl.model_dump())
        result_acl = ArtifactAcl(**stored_acl)
    except Exception:
        await _audit_artifact_share(
            ctx,
            operation="put_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact share update failed",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_UPDATE_FAILED", errorMessage="Artifact ACL update failed.")

    await _audit_artifact_share_best_effort(
        ctx,
        operation="put_artifact_share",
        artifact_type=artifact_type,
        slug=slug,
        decision="allow",
        reason=None,
        metadata={
            "old_acl": _acl_summary(old_acl),
            "new_acl": _acl_summary(result_acl.model_dump()),
        },
    )
    return Result(success=True, data=_share_from_acl(result_acl))


async def _load_artifact_acl_for_share(
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
    operation: Literal["get", "put"],
) -> ArtifactAcl | Result[ArtifactShare]:
    store = get_artifact_acl_store()
    if store is None:
        await _audit_artifact_share(
            ctx,
            operation=f"{operation}_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL store unavailable",
        )
        return _artifact_acl_unavailable()
    try:
        raw_acl = await store.get_acl(artifact_type=artifact_type, slug=slug)
        return ArtifactAcl(**raw_acl)
    except KeyError:
        await _audit_artifact_share(
            ctx,
            operation=f"{operation}_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL not found",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_NOT_FOUND", errorMessage="Artifact ACL not found.")
    except Exception:
        await _audit_artifact_share(
            ctx,
            operation=f"{operation}_artifact_share",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL query failed",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_QUERY_FAILED", errorMessage="Artifact ACL query failed.")


async def _can_manage_artifact_share(ctx: AppContext, acl: ArtifactAcl) -> bool:
    if ctx.user_id and ctx.user_id == acl.owner_user_id:
        return True
    decision = await authorize(
        ctx,
        action="module.admin.artifacts",
        resource=ResourceRef(type="artifact_acl", id=acl.owner_user_id),
    )
    return decision.allowed


async def _can_edit_artifact(
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
    acl: ArtifactAcl,
) -> bool:
    is_owner = bool(ctx.user_id and ctx.user_id == acl.owner_user_id)
    if is_owner:
        decision = await authorize(
            ctx,
            action=f"module.{artifact_type}.edit",
            resource=ResourceRef(type=artifact_type, id=slug),
        )
        if decision.allowed:
            return True

    admin_decision = await authorize(
        ctx,
        action="module.admin.artifacts",
        resource=ResourceRef(type="artifact_acl", id="module.admin.artifacts"),
    )
    return admin_decision.allowed


async def _artifact_list_items(
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    manifests: List[ArtifactManifest],
) -> List[ArtifactListItem]:
    store = get_artifact_acl_store()
    owner_display_names: dict[str, str | None] = {}
    items: list[ArtifactListItem] = []
    for manifest in manifests:
        owner_user_id = None
        owner_display_name = None
        can_manage_share = False
        can_edit = False
        if store is not None:
            try:
                raw_acl = await store.get_acl(artifact_type=artifact_type, slug=manifest.slug)
                acl = ArtifactAcl(**raw_acl)
                owner_user_id = acl.owner_user_id
                owner_display_name = await _artifact_owner_display_name(
                    owner_user_id,
                    cache=owner_display_names,
                )
                can_manage_share = await _can_manage_artifact_share(ctx, acl)
                can_edit = await _can_edit_artifact(
                    ctx,
                    artifact_type=artifact_type,
                    slug=manifest.slug,
                    acl=acl,
                )
            except Exception:
                can_manage_share = False
                can_edit = False
        items.append(
            ArtifactListItem(
                **manifest.model_dump(),
                owner_user_id=owner_user_id,
                owner_display_name=owner_display_name,
                can_manage_share=can_manage_share,
                can_edit=can_edit,
            )
        )
    return items


async def _artifact_owner_display_name(
    owner_user_id: str,
    *,
    cache: dict[str, str | None],
) -> str | None:
    if owner_user_id in cache:
        return cache[owner_user_id]

    try:
        record = await deps.get_enterprise_extensions().user_store.get_user(owner_user_id)
        display_name = _optional_str(record.get("display_name")) if record is not None else None
    except Exception:
        logger.warning("Artifact owner lookup failed for user_id=%s", owner_user_id, exc_info=True)
        display_name = None

    cache[owner_user_id] = display_name
    return display_name


async def _require_share_directory_access(
    ctx: AppContext,
    *,
    artifact_type: ShareArtifactType,
    target_type: Literal["user", "role"],
) -> None:
    permission_key = _share_directory_permission(artifact_type)
    decision = await authorize(
        ctx,
        action=permission_key,
        resource=ResourceRef(
            type="artifact_share_directory",
            id=f"{artifact_type}:{target_type}",
            attributes={"artifact_type": artifact_type, "target_type": target_type},
        ),
    )
    if decision.allowed:
        return

    await _audit_share_directory_best_effort(
        ctx,
        artifact_type=artifact_type,
        target_type=target_type,
        decision="deny",
        reason=decision.reason,
        metadata={"required_permission": permission_key},
    )
    raise HTTPException(status_code=403, detail=decision.reason or "Permission denied.")


def _share_directory_permission(artifact_type: ShareArtifactType) -> str:
    if artifact_type == "report":
        return "module.report.view"
    return "module.dashboard.view"


def _share_user_summary(record: dict[str, Any]) -> ArtifactShareUserSummary:
    return ArtifactShareUserSummary(
        user_id=str(record["user_id"]),
        display_name=_optional_str(record.get("display_name")),
        email=_optional_str(record.get("email")),
        department=_optional_str(record.get("department")),
        title=_optional_str(record.get("title")),
    )


def _share_role_summary(record: dict[str, Any]) -> ArtifactShareRoleSummary:
    return ArtifactShareRoleSummary(
        role_id=str(record["role_id"]),
        name=str(record.get("name") or record["role_id"]),
        description=_optional_str(record.get("description")),
        built_in=bool(record.get("built_in")),
    )


def _matches_directory_query(query: str, *values: str | None) -> bool:
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in value.casefold() for value in values if value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _share_from_acl(acl: ArtifactAcl) -> ArtifactShare:
    return ArtifactShare(
        owner_user_id=acl.owner_user_id,
        visibility=acl.visibility,
        allowed_roles=acl.allowed_roles,
        allowed_user_ids=acl.allowed_user_ids,
    )


async def _render_dashboard_html(
    svc: ServiceDep,
    ctx: AppContext,
    request: Request,
    slug: str,
    query_endpoint: str,
) -> Response:
    await require_artifact_access(ctx, artifact_type="dashboard", slug=slug, action="view")
    if not query_endpoint:
        base = str(request.base_url).rstrip("/")
        query_endpoint = f"{base}/api/v1/dashboard/query"

    result = await svc.dashboard.render_html(
        project_files_root=_project_files_root(svc),
        dashboard_slug=slug,
        query_endpoint=query_endpoint,
    )
    if not result.success or result.data is None:
        return _not_found_html("Dashboard", result.errorMessage)
    return HTMLResponse(content=result.data)


async def _render_report_html(svc: ServiceDep, ctx: AppContext, slug: str) -> Response:
    await require_artifact_access(ctx, artifact_type="report", slug=slug, action="view")
    result = await svc.report.render_html(project_files_root=_project_files_root(svc), report_slug=slug)
    if not result.success or result.data is None:
        return _not_found_html("Report", result.errorMessage)
    return HTMLResponse(content=result.data)


def _not_found_html(kind: str, message: str | None) -> HTMLResponse:
    error_html = (
        "<!doctype html><html><body style='font-family:sans-serif;padding:40px;text-align:center'>"
        f"<h2>{kind} not found</h2><p>{message or 'Unknown error'}</p>"
        "</body></html>"
    )
    return HTMLResponse(content=error_html, status_code=404)


async def _find_artifact(
    svc: ServiceDep,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
) -> ArtifactManifest | None:
    root = _project_files_root(svc)
    if artifact_type == "dashboard":
        result = await svc.dashboard.list_dashboards(project_files_root=root)
    else:
        result = await svc.report.list_reports(project_files_root=root)
    if not result.success:
        return None
    return next((manifest for manifest in result.data or [] if manifest.slug == slug), None)


def _artifact_not_found() -> Result[Any]:
    return Result(success=False, errorCode="RESOURCE_NOT_FOUND", errorMessage="Artifact not found.")


def _artifact_acl_unavailable() -> Result[Any]:
    return Result(
        success=False,
        errorCode="ARTIFACT_ACL_UNAVAILABLE",
        errorMessage="The configured enterprise extensions do not support artifact ACL management.",
    )


async def _get_existing_acl(store: Any, *, artifact_type: str, slug: str) -> dict[str, Any]:
    try:
        return await store.get_acl(artifact_type=artifact_type, slug=slug)
    except KeyError:
        return {}


async def _audit_artifact_acl(
    ctx: AppContext,
    *,
    operation: str,
    artifact_type: str,
    slug: str,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"operation": operation, **(metadata or {})}
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.artifacts",
            resource_type="artifact_acl",
            resource_id=f"{artifact_type}:{slug}",
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


async def _audit_artifact_acl_best_effort(
    ctx: AppContext,
    *,
    operation: str,
    artifact_type: str,
    slug: str,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await _audit_artifact_acl(
            ctx,
            operation=operation,
            artifact_type=artifact_type,
            slug=slug,
            decision=decision,
            reason=reason,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Artifact ACL audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


async def _audit_artifact_share(
    ctx: AppContext,
    *,
    operation: str,
    artifact_type: str,
    slug: str,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"operation": operation, **(metadata or {})}
    await audit_decision(
        ctx,
        AuditEvent(
            action="artifact.share",
            resource_type="artifact_acl",
            resource_id=f"{artifact_type}:{slug}",
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


async def _audit_artifact_share_best_effort(
    ctx: AppContext,
    *,
    operation: str,
    artifact_type: str,
    slug: str,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await _audit_artifact_share(
            ctx,
            operation=operation,
            artifact_type=artifact_type,
            slug=slug,
            decision=decision,
            reason=reason,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Artifact share audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


async def _audit_share_directory_best_effort(
    ctx: AppContext,
    *,
    artifact_type: str,
    target_type: str,
    decision: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="artifact.share.lookup",
                resource_type="artifact_share_directory",
                resource_id=f"{artifact_type}:{target_type}",
                decision=decision,
                reason=reason,
                metadata={"artifact_type": artifact_type, "target_type": target_type, **(metadata or {})},
            ),
        )
    except Exception as exc:
        logger.warning(
            "Artifact share directory audit write failed for target '%s' decision '%s': %s",
            target_type,
            decision,
            exc,
        )


def _acl_summary(raw_acl: Any) -> dict[str, Any]:
    if isinstance(raw_acl, ArtifactAcl):
        raw_acl = raw_acl.model_dump()
    if not isinstance(raw_acl, dict):
        return {}
    if not raw_acl:
        return {}
    return {
        "owner_user_id": _bounded_text(raw_acl.get("owner_user_id")),
        "visibility": _bounded_text(raw_acl.get("visibility")),
        "allowed_roles": _bounded_list(raw_acl.get("allowed_roles")),
        "allowed_user_ids": _bounded_list(raw_acl.get("allowed_user_ids")),
        "datasources": _bounded_list(raw_acl.get("datasources")),
    }


def _bounded_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_bounded_text(item) for item in value[:20] if isinstance(item, str)]


def _bounded_text(value: Any, *, max_length: int = 120) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _normalized_list(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized

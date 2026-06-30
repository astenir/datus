"""Enterprise report/dashboard artifact routes."""

from __future__ import annotations

from inspect import isawaitable
from pathlib import Path
from typing import Annotated, Any, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import get_artifact_acl_store, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import DashboardDetail
from datus.api.models.report_models import ReportDetail
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.utils.loggings import get_logger
from datus_enterprise.artifact_acl import filter_visible_artifacts, require_artifact_access
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import ResourceRef, authorize, require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])
logger = get_logger(__name__)


_require_dashboard_view = require_module("module.dashboard.view")
_require_report_view = require_module("module.report.view")
_require_admin_artifacts = require_module("module.admin.artifacts")
DashboardViewCtx = Annotated[AppContext, Depends(_require_dashboard_view)]
ReportViewCtx = Annotated[AppContext, Depends(_require_report_view)]
AdminArtifactsCtx = Annotated[AppContext, Depends(_require_admin_artifacts)]
ShareDirectoryCtx = Annotated[AppContext, Depends(deps.get_request_app_context)]
ShareArtifactType = Literal["report", "dashboard"]


class AdminArtifactSummary(BaseModel):
    """Admin artifact inventory item."""

    artifact_type: Literal["report", "dashboard"]
    manifest: ArtifactManifest


class ArtifactAcl(BaseModel):
    """Admin-managed ACL metadata for a report or dashboard artifact."""

    owner_user_id: str
    visibility: Literal["private", "role", "enterprise"]
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)
    datasources: list[str] = Field(default_factory=list)


class ArtifactShareUpdate(BaseModel):
    """Creator-managed sharing fields for a report or dashboard artifact."""

    visibility: Literal["private", "role", "enterprise"] = "private"
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class ArtifactShare(BaseModel):
    """Creator-visible ACL sharing state for one artifact."""

    owner_user_id: str
    visibility: Literal["private", "role", "enterprise"]
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class ArtifactShareUserSummary(BaseModel):
    """Sanitized user directory item for artifact sharing selectors."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None


class ArtifactShareRoleSummary(BaseModel):
    """Sanitized role directory item for artifact sharing selectors."""

    role_id: str
    name: str
    description: str | None = None
    built_in: bool = False


def _project_files_root(svc: ServiceDep) -> Path:
    return Path(svc.agent_config.project_root)


@router.get(
    "/dashboards",
    response_model=Result[List[ArtifactManifest]],
    summary="List Dashboard Artifacts",
    dependencies=[Depends(_require_dashboard_view)],
)
async def list_dashboards(svc: ServiceDep, ctx: DashboardViewCtx) -> Result[List[ArtifactManifest]]:
    result = await svc.dashboard.list_dashboards(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="dashboard", manifests=result.data)
    return Result(success=True, data=visible)


@router.get(
    "/dashboards/{slug}",
    response_model=Result[DashboardDetail],
    summary="Get Dashboard Artifact Detail",
    dependencies=[Depends(_require_dashboard_view)],
)
async def get_dashboard_detail(svc: ServiceDep, ctx: DashboardViewCtx, slug: str) -> Result[DashboardDetail]:
    await require_artifact_access(ctx, artifact_type="dashboard", slug=slug, action="view")
    return await svc.dashboard.get_detail(project_files_root=_project_files_root(svc), dashboard_slug=slug)


@router.get(
    "/dashboards/{slug}/acl",
    response_model=Result[ArtifactShare],
    summary="Get Dashboard Sharing ACL",
    dependencies=[Depends(_require_dashboard_view)],
)
async def get_dashboard_share_acl(svc: ServiceDep, ctx: DashboardViewCtx, slug: str) -> Result[ArtifactShare]:
    return await _get_creator_artifact_share(svc, ctx, artifact_type="dashboard", slug=slug)


@router.put(
    "/dashboards/{slug}/acl",
    response_model=Result[ArtifactShare],
    summary="Update Dashboard Sharing ACL",
    dependencies=[
        Depends(_require_dashboard_view),
        Depends(require_platform_active(operation="dashboard.artifact_acl.share", resource_type="artifact_acl")),
    ],
)
async def put_dashboard_share_acl(
    share: ArtifactShareUpdate,
    ctx: DashboardViewCtx,
    slug: str,
    request: Request,
) -> Result[ArtifactShare]:
    svc = await _resolve_request_service(request)
    return await _put_creator_artifact_share(svc, ctx, artifact_type="dashboard", slug=slug, share=share)


@router.get(
    "/dashboards/{slug}/html",
    response_class=HTMLResponse,
    summary="Get Dashboard HTML",
    dependencies=[Depends(_require_dashboard_view)],
)
async def get_dashboard_html_by_path(
    svc: ServiceDep,
    ctx: DashboardViewCtx,
    request: Request,
    slug: str,
    query_endpoint: str = Query(default="", description="Override query endpoint URL (empty = auto-detect)"),
) -> Response:
    return await _render_dashboard_html(svc, ctx, request, slug, query_endpoint)


@router.get(
    "/reports",
    response_model=Result[List[ArtifactManifest]],
    summary="List Report Artifacts",
    dependencies=[Depends(_require_report_view)],
)
async def list_reports(svc: ServiceDep, ctx: ReportViewCtx) -> Result[List[ArtifactManifest]]:
    result = await svc.report.list_reports(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="report", manifests=result.data)
    return Result(success=True, data=visible)


@router.get(
    "/reports/{slug}",
    response_model=Result[ReportDetail],
    summary="Get Report Artifact Detail",
    dependencies=[Depends(_require_report_view)],
)
async def get_report_detail(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Result[ReportDetail]:
    await require_artifact_access(ctx, artifact_type="report", slug=slug, action="view")
    return await svc.report.get_detail(project_files_root=_project_files_root(svc), report_slug=slug)


@router.get(
    "/reports/{slug}/acl",
    response_model=Result[ArtifactShare],
    summary="Get Report Sharing ACL",
    dependencies=[Depends(_require_report_view)],
)
async def get_report_share_acl(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Result[ArtifactShare]:
    return await _get_creator_artifact_share(svc, ctx, artifact_type="report", slug=slug)


@router.put(
    "/reports/{slug}/acl",
    response_model=Result[ArtifactShare],
    summary="Update Report Sharing ACL",
    dependencies=[
        Depends(_require_report_view),
        Depends(require_platform_active(operation="report.artifact_acl.share", resource_type="artifact_acl")),
    ],
)
async def put_report_share_acl(
    share: ArtifactShareUpdate,
    ctx: ReportViewCtx,
    slug: str,
    request: Request,
) -> Result[ArtifactShare]:
    svc = await _resolve_request_service(request)
    return await _put_creator_artifact_share(svc, ctx, artifact_type="report", slug=slug, share=share)


@router.get(
    "/reports/{slug}/html",
    response_class=HTMLResponse,
    summary="Get Report HTML",
    dependencies=[Depends(_require_report_view)],
)
async def get_report_html_by_path(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Response:
    return await _render_report_html(svc, ctx, slug)


@router.get(
    "/artifact-share/users",
    response_model=Result[List[ArtifactShareUserSummary]],
    summary="List Artifact Share Users",
)
async def list_artifact_share_users(
    ctx: ShareDirectoryCtx,
    artifact_type: Annotated[ShareArtifactType, Query(description="Artifact kind the selector is used for.")],
    query: Annotated[str, Query(max_length=200, description="Case-insensitive user search text.")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    include_self: Annotated[bool, Query(description="Include the current user in selector results.")] = False,
) -> Result[List[ArtifactShareUserSummary]]:
    """Return a sanitized enabled-user directory for creator self-service sharing."""

    await _require_share_directory_access(ctx, artifact_type=artifact_type, target_type="user")
    try:
        records = await deps.get_enterprise_extensions().user_store.list_users(enabled=True)
    except Exception:
        await _audit_share_directory_best_effort(
            ctx,
            artifact_type=artifact_type,
            target_type="user",
            decision="deny",
            reason="user directory query failed",
            metadata={"query_present": bool(query.strip())},
        )
        return Result(
            success=False,
            errorCode="ARTIFACT_SHARE_USER_DIRECTORY_FAILED",
            errorMessage="Artifact share user directory query failed.",
        )

    normalized_query = query.strip()
    users: list[ArtifactShareUserSummary] = []
    for record in records:
        summary = _share_user_summary(record)
        if not include_self and ctx.user_id and summary.user_id == ctx.user_id:
            continue
        if not _matches_directory_query(
            normalized_query,
            summary.user_id,
            summary.display_name,
            summary.email,
            summary.department,
            summary.title,
        ):
            continue
        users.append(summary)
        if len(users) >= limit:
            break

    await _audit_share_directory_best_effort(
        ctx,
        artifact_type=artifact_type,
        target_type="user",
        decision="allow",
        reason=None,
        metadata={"query_present": bool(normalized_query), "count": len(users), "include_self": include_self},
    )
    return Result(success=True, data=users)


@router.get(
    "/artifact-share/roles",
    response_model=Result[List[ArtifactShareRoleSummary]],
    summary="List Artifact Share Roles",
)
async def list_artifact_share_roles(
    ctx: ShareDirectoryCtx,
    artifact_type: Annotated[ShareArtifactType, Query(description="Artifact kind the selector is used for.")],
    query: Annotated[str, Query(max_length=200, description="Case-insensitive role search text.")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Result[List[ArtifactShareRoleSummary]]:
    """Return a sanitized role directory for creator self-service sharing."""

    await _require_share_directory_access(ctx, artifact_type=artifact_type, target_type="role")
    try:
        records = await deps.get_enterprise_extensions().role_store.list_roles()
    except Exception:
        await _audit_share_directory_best_effort(
            ctx,
            artifact_type=artifact_type,
            target_type="role",
            decision="deny",
            reason="role directory query failed",
            metadata={"query_present": bool(query.strip())},
        )
        return Result(
            success=False,
            errorCode="ARTIFACT_SHARE_ROLE_DIRECTORY_FAILED",
            errorMessage="Artifact share role directory query failed.",
        )

    normalized_query = query.strip()
    roles: list[ArtifactShareRoleSummary] = []
    for record in records:
        summary = _share_role_summary(record)
        if not _matches_directory_query(normalized_query, summary.role_id, summary.name, summary.description):
            continue
        roles.append(summary)
        if len(roles) >= limit:
            break

    await _audit_share_directory_best_effort(
        ctx,
        artifact_type=artifact_type,
        target_type="role",
        decision="allow",
        reason=None,
        metadata={"query_present": bool(normalized_query), "count": len(roles)},
    )
    return Result(success=True, data=roles)


@router.get(
    "/admin/artifacts",
    response_model=Result[List[AdminArtifactSummary]],
    summary="List Admin Artifacts",
    dependencies=[Depends(_require_admin_artifacts)],
)
async def list_admin_artifacts(svc: ServiceDep, ctx: AdminArtifactsCtx) -> Result[List[AdminArtifactSummary]]:
    """Return all report/dashboard manifests for admin inventory workflows."""

    root = _project_files_root(svc)
    dashboards = await svc.dashboard.list_dashboards(project_files_root=root)
    if not dashboards.success:
        return Result(success=False, errorCode=dashboards.errorCode, errorMessage=dashboards.errorMessage)
    reports = await svc.report.list_reports(project_files_root=root)
    if not reports.success:
        return Result(success=False, errorCode=reports.errorCode, errorMessage=reports.errorMessage)

    items = [
        *(AdminArtifactSummary(artifact_type="dashboard", manifest=manifest) for manifest in dashboards.data or []),
        *(AdminArtifactSummary(artifact_type="report", manifest=manifest) for manifest in reports.data or []),
    ]
    items.sort(
        key=lambda item: (item.manifest.updated_at or item.manifest.created_at or "", item.artifact_type), reverse=True
    )
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.artifacts",
                resource_type="artifact",
                resource_id=None,
                decision="allow",
                metadata={"operation": "list_admin_artifacts", "count": len(items)},
            ),
        )
    except Exception as exc:
        logger.warning("Admin artifact list audit write failed: %s", exc)
    return Result(success=True, data=items)


@router.get(
    "/admin/artifacts/{artifact_type}/{slug}/acl",
    response_model=Result[ArtifactAcl],
    summary="Get Artifact ACL",
    dependencies=[Depends(_require_admin_artifacts)],
)
async def get_admin_artifact_acl(
    svc: ServiceDep,
    ctx: AdminArtifactsCtx,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
) -> Result[ArtifactAcl]:
    """Return stored ACL metadata for one managed artifact."""

    artifact = await _find_artifact(svc, artifact_type=artifact_type, slug=slug)
    if artifact is None:
        await _audit_artifact_acl(
            ctx,
            operation="get_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact not found",
        )
        return _artifact_not_found()

    store = get_artifact_acl_store()
    if store is None:
        await _audit_artifact_acl(
            ctx,
            operation="get_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL store unavailable",
        )
        return _artifact_acl_unavailable()

    try:
        raw_acl = await store.get_acl(artifact_type=artifact_type, slug=slug)
        acl = ArtifactAcl(**raw_acl)
    except KeyError:
        await _audit_artifact_acl(
            ctx,
            operation="get_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL not found",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_NOT_FOUND", errorMessage="Artifact ACL not found.")
    except Exception:
        await _audit_artifact_acl(
            ctx,
            operation="get_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL query failed",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_QUERY_FAILED", errorMessage="Artifact ACL query failed.")

    await _audit_artifact_acl(
        ctx,
        operation="get_artifact_acl",
        artifact_type=artifact_type,
        slug=slug,
        decision="allow",
        reason=None,
    )
    return Result(success=True, data=acl)


@router.put(
    "/admin/artifacts/{artifact_type}/{slug}/acl",
    response_model=Result[ArtifactAcl],
    summary="Update Artifact ACL",
    dependencies=[
        Depends(_require_admin_artifacts),
        Depends(require_platform_active(operation="admin.artifacts.acl.update", resource_type="artifact_acl")),
    ],
)
async def put_admin_artifact_acl(
    acl: ArtifactAcl,
    ctx: AdminArtifactsCtx,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
    request: Request,
) -> Result[ArtifactAcl]:
    """Persist ACL metadata for one managed artifact."""

    svc = await _resolve_request_service(request)
    artifact = await _find_artifact(svc, artifact_type=artifact_type, slug=slug)
    if artifact is None:
        await _audit_artifact_acl(
            ctx,
            operation="put_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact not found",
        )
        return _artifact_not_found()

    store = get_artifact_acl_store()
    if store is None:
        await _audit_artifact_acl(
            ctx,
            operation="put_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL store unavailable",
        )
        return _artifact_acl_unavailable()

    try:
        old_acl = await _get_existing_acl(store, artifact_type=artifact_type, slug=slug)
        stored_acl = await store.put_acl(artifact_type=artifact_type, slug=slug, acl=acl.model_dump())
        result_acl = ArtifactAcl(**stored_acl)
    except Exception:
        await _audit_artifact_acl(
            ctx,
            operation="put_artifact_acl",
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="artifact ACL update failed",
        )
        return Result(success=False, errorCode="ARTIFACT_ACL_UPDATE_FAILED", errorMessage="Artifact ACL update failed.")

    await _audit_artifact_acl_best_effort(
        ctx,
        operation="put_artifact_acl",
        artifact_type=artifact_type,
        slug=slug,
        decision="allow",
        reason=None,
        metadata={
            "old_acl": _acl_summary(old_acl),
            "new_acl": _acl_summary(result_acl.model_dump()),
        },
    )
    return Result(success=True, data=result_acl)


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

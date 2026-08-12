"""Enterprise report and dashboard browsing routes."""

from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import (
    get_artifact_acl_store,
    require_any_module,
    require_platform_active,
)
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import DashboardDetail
from datus.api.models.downstream import ReportEditSession
from datus.api.models.report_models import ReportDetail
from datus.utils.loggings import get_logger
from datus_enterprise.artifacts.acl import (
    filter_visible_artifacts,
    require_artifact_access,
    require_artifact_edit_access,
)
from datus_enterprise.artifacts.context import (
    DashboardViewCtx,
    ReportViewCtx,
    ShareDirectoryCtx,
    _require_dashboard_view,
    _require_report_view,
)
from datus_enterprise.artifacts.helpers import (
    _artifact_list_items,
    _project_files_root,
    _render_dashboard_html,
    _render_report_html,
)
from datus_enterprise.artifacts.models import (
    ArtifactListItem,
)
from datus_enterprise.audit import AuditEvent, audit_decision

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])
logger = get_logger(__name__)

_require_report_delete = require_any_module("module.report.edit", "module.admin.artifacts")
_require_dashboard_delete = require_any_module("module.dashboard.edit", "module.admin.artifacts")


@router.get(
    "/dashboards",
    response_model=Result[List[ArtifactListItem]],
    summary="List Dashboard Artifacts",
    dependencies=[Depends(_require_dashboard_view)],
)
async def list_dashboards(svc: ServiceDep, ctx: DashboardViewCtx) -> Result[List[ArtifactListItem]]:
    result = await svc.dashboard.list_dashboards(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="dashboard", manifests=result.data)
    items = await _artifact_list_items(ctx, artifact_type="dashboard", manifests=visible)
    return Result(success=True, data=items)


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
    response_model=Result[List[ArtifactListItem]],
    summary="List Report Artifacts",
    dependencies=[Depends(_require_report_view)],
)
async def list_reports(svc: ServiceDep, ctx: ReportViewCtx) -> Result[List[ArtifactListItem]]:
    result = await svc.report.list_reports(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="report", manifests=result.data)
    items = await _artifact_list_items(ctx, artifact_type="report", manifests=visible)
    return Result(success=True, data=items)


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
    "/report/detail",
    response_model=Result[ReportDetail],
    summary="Get Report Artifact Detail",
    dependencies=[Depends(_require_report_view)],
)
async def get_report_detail_legacy(
    svc: ServiceDep,
    ctx: ReportViewCtx,
    slug: str = Query(..., description="Report slug, e.g. 'account_activity_q1'"),
) -> Result[ReportDetail]:
    """Keep the upstream detail path behind the downstream artifact ACL boundary."""
    await require_artifact_access(ctx, artifact_type="report", slug=slug, action="view")
    return await svc.report.get_detail(project_files_root=_project_files_root(svc), report_slug=slug)


@router.post(
    "/reports/{slug}/edit-sessions",
    response_model=Result[ReportEditSession],
    summary="Create Report Edit Session",
    dependencies=[Depends(require_platform_active(operation="report.edit_session.create", resource_type="report"))],
)
async def create_report_edit_session(
    svc: ServiceDep,
    ctx: ShareDirectoryCtx,
    slug: str,
) -> Result[ReportEditSession]:
    await require_artifact_edit_access(ctx, artifact_type="report", slug=slug)
    detail = await svc.report.get_detail(project_files_root=_project_files_root(svc), report_slug=slug)
    if not detail.success:
        return Result(
            success=False,
            errorCode=detail.errorCode or "REPORT_NOT_FOUND",
            errorMessage=detail.errorMessage or "Report not found.",
        )

    session = svc.task_manager.create_report_edit_session(user_id=ctx.user_id, report_slug=slug)
    return Result(success=True, data=session)


@router.get(
    "/reports/{slug}/html",
    response_class=HTMLResponse,
    summary="Get Report HTML",
    dependencies=[Depends(_require_report_view)],
)
async def get_report_html_by_path(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Response:
    return await _render_report_html(svc, ctx, slug)


@router.delete(
    "/reports/{slug}",
    response_model=Result[bool],
    summary="Delete Report Artifact",
    description=(
        "Permanently delete a report artifact directory and its share ACL. "
        "Requires owner or module.admin.artifacts edit authorization; refused while "
        "an unexpired report edit session is still active."
    ),
    dependencies=[
        Depends(_require_report_delete),
        Depends(require_platform_active(operation="report.delete", resource_type="report")),
    ],
)
async def delete_report_artifact(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Result[bool]:
    await require_artifact_edit_access(ctx, artifact_type="report", slug=slug)
    return await _delete_artifact(svc, ctx, artifact_type="report", slug=slug)


@router.delete(
    "/dashboards/{slug}",
    response_model=Result[bool],
    summary="Delete Dashboard Artifact",
    description=(
        "Permanently delete a dashboard artifact directory and its share ACL. "
        "Requires owner or module.admin.artifacts edit authorization; refused while "
        "an unexpired dashboard edit session is still active."
    ),
    dependencies=[
        Depends(_require_dashboard_delete),
        Depends(require_platform_active(operation="dashboard.delete", resource_type="dashboard")),
    ],
)
async def delete_dashboard_artifact(svc: ServiceDep, ctx: DashboardViewCtx, slug: str) -> Result[bool]:
    await require_artifact_edit_access(ctx, artifact_type="dashboard", slug=slug)
    return await _delete_artifact(svc, ctx, artifact_type="dashboard", slug=slug)


async def _delete_artifact(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    artifact_type: Literal["report", "dashboard"],
    slug: str,
) -> Result[bool]:
    """Delete the on-disk artifact, then its share ACL, with audit."""

    if _has_active_artifact_edit_session(svc, artifact_type=artifact_type, slug=slug):
        await _audit_artifact_delete(
            ctx,
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason="active artifact edit session",
        )
        return Result(
            success=False,
            errorCode="EDIT_SESSION_ACTIVE",
            errorMessage=f"{artifact_type} {slug!r} is being edited; try again later.",
        )

    project_files_root = _project_files_root(svc)
    if artifact_type == "report":
        result = await svc.report.delete_report(project_files_root=project_files_root, report_slug=slug)
    else:
        result = await svc.dashboard.delete_dashboard(project_files_root=project_files_root, dashboard_slug=slug)

    if not result.success:
        await _audit_artifact_delete(
            ctx,
            artifact_type=artifact_type,
            slug=slug,
            decision="deny",
            reason=str(result.errorCode),
        )
        return result

    await _delete_artifact_acl(artifact_type=artifact_type, slug=slug)
    await _audit_artifact_delete(ctx, artifact_type=artifact_type, slug=slug, decision="allow")
    return result


def _has_active_artifact_edit_session(
    svc: ServiceDep,
    *,
    artifact_type: str,
    slug: str,
) -> bool:
    task_manager = getattr(svc, "task_manager", None)
    check = getattr(task_manager, "has_active_artifact_edit_session", None)
    if check is None:
        return False
    return check(artifact_type=artifact_type, slug=slug)


async def _delete_artifact_acl(*, artifact_type: str, slug: str) -> None:
    store = get_artifact_acl_store()
    if store is None:
        return
    try:
        await store.delete_acl(artifact_type=artifact_type, slug=slug)
    except Exception as exc:
        logger.warning(
            "Failed to delete artifact ACL for %s/%s: %s",
            artifact_type,
            slug,
            exc,
        )


async def _audit_artifact_delete(
    ctx: AppContext,
    *,
    artifact_type: str,
    slug: str,
    decision: str,
    reason: str | None = None,
) -> None:
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="artifact.delete",
                resource_type=artifact_type,
                resource_id=slug,
                decision=decision,
                reason=reason,
            ),
        )
    except Exception as exc:
        logger.warning(
            "Artifact delete audit failed for %s/%s decision=%s: %s",
            artifact_type,
            slug,
            decision,
            exc,
        )

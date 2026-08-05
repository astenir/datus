"""Enterprise report and dashboard browsing routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse

from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_platform_active
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

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])
logger = get_logger(__name__)


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

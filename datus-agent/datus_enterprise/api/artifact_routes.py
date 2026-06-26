"""Enterprise report/dashboard artifact routes."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, List, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import DashboardDetail
from datus.api.models.report_models import ReportDetail
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.artifact_acl import filter_visible_artifacts, require_artifact_access
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])


DashboardViewCtx = Annotated[AppContext, Depends(require_module("module.dashboard.view"))]
ReportViewCtx = Annotated[AppContext, Depends(require_module("module.report.view"))]
AdminArtifactsCtx = Annotated[AppContext, Depends(require_module("module.admin.artifacts"))]


class AdminArtifactSummary(BaseModel):
    """Admin artifact inventory item."""

    artifact_type: Literal["report", "dashboard"]
    manifest: ArtifactManifest


def _project_files_root(svc: ServiceDep) -> Path:
    return Path(svc.agent_config.project_root)


@router.get("/dashboards", response_model=Result[List[ArtifactManifest]], summary="List Dashboard Artifacts")
async def list_dashboards(svc: ServiceDep, ctx: DashboardViewCtx) -> Result[List[ArtifactManifest]]:
    result = await svc.dashboard.list_dashboards(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="dashboard", manifests=result.data)
    return Result(success=True, data=visible)


@router.get("/dashboards/{slug}", response_model=Result[DashboardDetail], summary="Get Dashboard Artifact Detail")
async def get_dashboard_detail(svc: ServiceDep, ctx: DashboardViewCtx, slug: str) -> Result[DashboardDetail]:
    await require_artifact_access(ctx, artifact_type="dashboard", slug=slug, action="view")
    return await svc.dashboard.get_detail(project_files_root=_project_files_root(svc), dashboard_slug=slug)


@router.get("/dashboards/{slug}/html", response_class=HTMLResponse, summary="Get Dashboard HTML")
async def get_dashboard_html_by_path(
    svc: ServiceDep,
    ctx: DashboardViewCtx,
    request: Request,
    slug: str,
    query_endpoint: str = Query(default="", description="Override query endpoint URL (empty = auto-detect)"),
) -> Response:
    return await _render_dashboard_html(svc, ctx, request, slug, query_endpoint)


@router.get("/reports", response_model=Result[List[ArtifactManifest]], summary="List Report Artifacts")
async def list_reports(svc: ServiceDep, ctx: ReportViewCtx) -> Result[List[ArtifactManifest]]:
    result = await svc.report.list_reports(project_files_root=_project_files_root(svc))
    if not result.success or result.data is None:
        return result
    visible = await filter_visible_artifacts(ctx, artifact_type="report", manifests=result.data)
    return Result(success=True, data=visible)


@router.get("/reports/{slug}", response_model=Result[ReportDetail], summary="Get Report Artifact Detail")
async def get_report_detail(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Result[ReportDetail]:
    await require_artifact_access(ctx, artifact_type="report", slug=slug, action="view")
    return await svc.report.get_detail(project_files_root=_project_files_root(svc), report_slug=slug)


@router.get("/reports/{slug}/html", response_class=HTMLResponse, summary="Get Report HTML")
async def get_report_html_by_path(svc: ServiceDep, ctx: ReportViewCtx, slug: str) -> Response:
    return await _render_report_html(svc, ctx, slug)


@router.get("/admin/artifacts", response_model=Result[List[AdminArtifactSummary]], summary="List Admin Artifacts")
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
    return Result(success=True, data=items)


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

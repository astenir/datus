"""API routes for the visual-report artifact.

* ``GET /api/v1/report/detail`` — returns the render/ tree (app.jsx + sibling
  modules) plus the full set of queries/*.sql and queries/*.json files for
  a report produced by the ``gen_visual_report`` subagent.

Publish and the companion ``ask_report`` subagent are not part of the
agent contract — they live in a separate SaaS host that wraps this
service when present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep, get_request_app_context
from datus.api.enterprise.deps import require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.report_models import ReportDetail, ReportEditSession
from datus_enterprise.artifact_acl import require_artifact_access, require_artifact_edit_access

router = APIRouter(prefix="/api/v1", tags=["report"])
ReportViewModuleCtx = Annotated[AppContext, Depends(require_module("module.report.view"))]
ReportEditCtx = Annotated[AppContext, Depends(get_request_app_context)]


def _project_files_root(svc: ServiceDep) -> Path:
    """Anchor for ``reports/<slug>/``; matches where
    ``gen_visual_report`` wrote the artifact (CWD in CLI; the
    workspace's project files dir when a SaaS host overrides it)."""
    return Path(svc.agent_config.project_root)


@router.get(
    "/report/detail",
    response_model=Result[ReportDetail],
    summary="Get Report Artifact Detail",
    description=(
        "Return the render/ tree (app.jsx + sibling modules) plus the full set of "
        "queries/*.sql and queries/*.json files for a report produced by the "
        "gen_visual_report subagent."
    ),
)
async def get_report_detail(
    ctx: ReportViewModuleCtx,
    svc: ServiceDep,
    slug: str = Query(..., description="Report slug, e.g. 'account_activity_q1'"),
) -> Result[ReportDetail]:
    await require_artifact_access(ctx, artifact_type="report", slug=slug, action="view")
    return await svc.report.get_detail(
        project_files_root=_project_files_root(svc),
        report_slug=slug,
    )


@router.post(
    "/reports/{slug}/edit-sessions",
    response_model=Result[ReportEditSession],
    summary="Create Report Edit Session",
    description=(
        "Create an ephemeral, ACL-bound edit subagent for one report. The returned "
        "subagent_id can be passed to /api/v1/chat/stream; it is locked to reports/<slug>/."
    ),
    dependencies=[Depends(require_platform_active(operation="report.edit_session.create", resource_type="report"))],
)
async def create_report_edit_session(
    ctx: ReportEditCtx,
    svc: ServiceDep,
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

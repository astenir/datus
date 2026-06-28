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
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_module
from datus.api.models.base_models import Result
from datus.api.models.report_models import ReportDetail
from datus_enterprise.artifact_acl import require_artifact_access

router = APIRouter(prefix="/api/v1", tags=["report"])
ReportViewModuleCtx = Annotated[AppContext, Depends(require_module("module.report.view"))]


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

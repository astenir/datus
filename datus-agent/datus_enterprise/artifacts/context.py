"""Shared FastAPI dependencies for enterprise Artifact routes."""

from typing import Annotated

from fastapi import Depends

from datus.api import deps
from datus.api.auth.context import AppContext
from datus_enterprise.authorization import require_module

_require_dashboard_view = require_module("module.dashboard.view")
_require_report_view = require_module("module.report.view")
_require_admin_artifacts = require_module("module.admin.artifacts")

DashboardViewCtx = Annotated[AppContext, Depends(_require_dashboard_view)]
ReportViewCtx = Annotated[AppContext, Depends(_require_report_view)]
AdminArtifactsCtx = Annotated[AppContext, Depends(_require_admin_artifacts)]
ShareDirectoryCtx = Annotated[AppContext, Depends(deps.get_request_app_context)]

"""Compatibility router for the split enterprise Artifact API domain."""

from fastapi import APIRouter

from datus.api import deps
from datus_enterprise.artifacts.admin_routes import (
    get_admin_artifact_acl,
    list_admin_artifacts,
    put_admin_artifact_acl,
)
from datus_enterprise.artifacts.admin_routes import (
    router as admin_router,
)
from datus_enterprise.artifacts.browse_routes import (
    create_report_edit_session,
    get_dashboard_detail,
    get_dashboard_html_by_path,
    get_report_detail,
    get_report_detail_legacy,
    get_report_html_by_path,
    list_dashboards,
    list_reports,
)
from datus_enterprise.artifacts.browse_routes import (
    router as browse_router,
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
from datus_enterprise.artifacts.share_routes import (
    get_dashboard_share_acl,
    get_report_share_acl,
    list_artifact_share_roles,
    list_artifact_share_users,
    put_dashboard_share_acl,
    put_report_share_acl,
)
from datus_enterprise.artifacts.share_routes import (
    router as share_router,
)

router = APIRouter()
router.include_router(browse_router)
router.include_router(share_router)
router.include_router(admin_router)

__all__ = [
    "AdminArtifactSummary",
    "ArtifactAcl",
    "ArtifactListItem",
    "ArtifactShare",
    "ArtifactShareRoleSummary",
    "ArtifactShareUpdate",
    "ArtifactShareUserSummary",
    "ShareArtifactType",
    "create_report_edit_session",
    "deps",
    "get_admin_artifact_acl",
    "get_dashboard_detail",
    "get_dashboard_html_by_path",
    "get_dashboard_share_acl",
    "get_report_detail",
    "get_report_detail_legacy",
    "get_report_html_by_path",
    "get_report_share_acl",
    "list_admin_artifacts",
    "list_artifact_share_roles",
    "list_artifact_share_users",
    "list_dashboards",
    "list_reports",
    "put_admin_artifact_acl",
    "put_dashboard_share_acl",
    "put_report_share_acl",
    "router",
]

"""Enterprise Artifact creator-sharing and directory routes."""

from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, Request

from datus.api import deps
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus.utils.loggings import get_logger
from datus_enterprise.artifacts.context import (
    DashboardViewCtx,
    ReportViewCtx,
    ShareDirectoryCtx,
    _require_dashboard_view,
    _require_report_view,
)
from datus_enterprise.artifacts.helpers import (
    _audit_share_directory_best_effort,
    _get_creator_artifact_share,
    _matches_directory_query,
    _put_creator_artifact_share,
    _require_share_directory_access,
    _resolve_request_service,
    _share_role_summary,
    _share_user_summary,
)
from datus_enterprise.artifacts.models import (
    ArtifactShare,
    ArtifactShareRoleSummary,
    ArtifactShareUpdate,
    ArtifactShareUserSummary,
    ShareArtifactType,
)

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])
logger = get_logger(__name__)


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

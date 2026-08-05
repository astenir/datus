"""Enterprise Artifact inventory and ACL administration routes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import get_artifact_acl_store, require_platform_active
from datus.api.models.base_models import Result
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.utils.loggings import get_logger
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.artifacts.context import (
    AdminArtifactsCtx,
    _require_admin_artifacts,
)
from datus_enterprise.artifacts.helpers import (
    _acl_summary,
    _admin_artifact_matches_search,
    _artifact_acl_unavailable,
    _artifact_not_found,
    _audit_artifact_acl,
    _audit_artifact_acl_best_effort,
    _find_artifact,
    _get_existing_acl,
    _project_files_root,
    _resolve_request_service,
)
from datus_enterprise.artifacts.models import (
    AdminArtifactSummary,
    ArtifactAcl,
)
from datus_enterprise.audit import AuditEvent, audit_decision

router = APIRouter(prefix="/api/v1", tags=["enterprise-artifacts"])
logger = get_logger(__name__)


@router.get(
    "/admin/artifacts",
    response_model=AdminListResult[AdminArtifactSummary],
    summary="List Admin Artifacts",
    dependencies=[Depends(_require_admin_artifacts)],
)
async def list_admin_artifacts(
    svc: ServiceDep,
    ctx: AdminArtifactsCtx,
    artifact_type: Annotated[Literal["report", "dashboard"] | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search artifact manifest fields.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminArtifactSummary] | Result[Any]:
    """Return all report/dashboard manifests for admin inventory workflows."""

    root = _project_files_root(svc)
    dashboard_manifests: list[ArtifactManifest] = []
    report_manifests: list[ArtifactManifest] = []
    if artifact_type != "report":
        dashboards = await svc.dashboard.list_dashboards(project_files_root=root)
        if not dashboards.success:
            return Result(success=False, errorCode=dashboards.errorCode, errorMessage=dashboards.errorMessage)
        dashboard_manifests = dashboards.data or []
    if artifact_type != "dashboard":
        reports = await svc.report.list_reports(project_files_root=root)
        if not reports.success:
            return Result(success=False, errorCode=reports.errorCode, errorMessage=reports.errorMessage)
        report_manifests = reports.data or []

    items = [
        *(AdminArtifactSummary(artifact_type="dashboard", manifest=manifest) for manifest in dashboard_manifests),
        *(AdminArtifactSummary(artifact_type="report", manifest=manifest) for manifest in report_manifests),
    ]
    items.sort(
        key=lambda item: (item.manifest.updated_at or item.manifest.created_at or "", item.artifact_type), reverse=True
    )
    items = [item for item in items if _admin_artifact_matches_search(item, search)]
    page = paginate_admin_records(items, limit=limit, offset=offset)
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="module.admin.artifacts",
                resource_type="artifact",
                resource_id=None,
                decision="allow",
                metadata={
                    "operation": "list_admin_artifacts",
                    "count": len(page.data or []),
                    "artifact_type": artifact_type,
                    "offset": offset,
                    "has_more": page.pagination.has_more,
                },
            ),
        )
    except Exception as exc:
        logger.warning("Admin artifact list audit write failed: %s", exc)
    return page


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

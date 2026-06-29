"""
API routes for enterprise-safe subject tree discovery.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.explorer_models import (
    CreateDirectoryInput,
    DeleteSubjectInput,
    EditMetricInput,
    EditSemanticModelInput,
    MetricDimensionsData,
    MetricInfo,
    MetricPreviewData,
    MetricPreviewInput,
    ReferenceSQLInfo,
    ReferenceSQLInput,
    RenameSubjectInput,
    SubjectListData,
    SubjectPathInput,
)
from datus.api.services.explorer_service import ExplorerService
from datus.utils.exceptions import DatusException

router = APIRouter(prefix="/api/v1", tags=["subject"])
_require_catalog_module = require_module("module.datasource_catalog")
_require_config_edit = require_module("module.config.edit")
CatalogModuleCtx = Annotated[AppContext, Depends(_require_catalog_module)]
ConfigEditCtx = Annotated[AppContext, Depends(_require_config_edit)]

DATASOURCE_QUERY = Query("", description="Datasource to list subject tree from")


async def _project_explorer(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    datasource_id: Optional[str],
) -> ExplorerService:
    try:
        projection = await project_request_config(
            ctx,
            svc.agent_config,
            operation="catalog.subject_tree",
            requested_datasource=datasource_id or None,
        )
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExplorerService(projection.config)


@router.get(
    "/subject-tree",
    response_model=Result[SubjectListData],
    summary="List Subject Tree",
    description="List subject directories, metrics, and reference SQL entries for an authorized datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def list_subject_tree(
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[SubjectListData]:
    """List the readonly subject tree through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.get_subject_list()


@router.post(
    "/subject-tree/create",
    response_model=Result[dict],
    summary="Create Subject Directory",
    description="Create a directory in the subject tree for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.create", resource_type="subject_tree")),
    ],
)
async def create_directory(
    request: CreateDirectoryInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Create a subject directory through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.create_directory(request)


@router.post(
    "/subject-tree/rename",
    response_model=Result[dict],
    summary="Rename Subject",
    description="Rename or move a subject tree node for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.rename", resource_type="subject_tree")),
    ],
)
async def rename_subject(
    request: RenameSubjectInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Rename or move a subject tree node through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.rename_subject(request)


@router.delete(
    "/subject-tree/delete",
    response_model=Result[dict],
    summary="Delete Subject",
    description="Delete a subject tree node for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.delete", resource_type="subject_tree")),
    ],
)
async def delete_subject(
    request: DeleteSubjectInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Delete a subject tree node through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.delete_subject(request)


@router.post(
    "/subject-tree/metric",
    response_model=Result[MetricInfo],
    summary="Get Subject Metric",
    description="Get a metric definition from the subject tree for an authorized datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_metric(
    request: SubjectPathInput,
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[MetricInfo]:
    """Get metric information through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.get_metric(request.subject_path)


@router.post(
    "/subject-tree/metric/dimensions",
    response_model=Result[MetricDimensionsData],
    summary="Get Subject Metric Dimensions",
    description="List queryable dimensions for a subject metric on an authorized datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_metric_dimensions(
    request: SubjectPathInput,
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[MetricDimensionsData]:
    """Get metric dimensions through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.get_metric_dimensions(request.subject_path)


@router.post(
    "/subject-tree/metric/preview",
    response_model=Result[MetricPreviewData],
    summary="Preview Subject Metric",
    description="Compile a subject metric preview for an authorized datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def preview_metric(
    request: MetricPreviewInput,
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[MetricPreviewData]:
    """Preview a metric through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.preview_metric(request)


@router.post(
    "/subject-tree/metric/create",
    response_model=Result[dict],
    summary="Create Subject Metric",
    description="Create a metric definition for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.metric.create", resource_type="subject_tree")),
    ],
)
async def create_metric(
    request: EditMetricInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Create a metric through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.create_metric(request)


@router.post(
    "/subject-tree/metric/edit",
    response_model=Result[dict],
    summary="Edit Subject Metric",
    description="Edit a metric definition for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.metric.edit", resource_type="subject_tree")),
    ],
)
async def edit_metric(
    request: EditMetricInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Edit a metric through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.edit_metric(request)


@router.post(
    "/subject-tree/reference_sql",
    response_model=Result[ReferenceSQLInfo],
    summary="Get Subject Reference SQL",
    description="Get reference SQL from the subject tree for an authorized datasource",
    dependencies=[Depends(_require_catalog_module)],
)
async def get_reference_sql(
    request: SubjectPathInput,
    svc: ServiceDep,
    ctx: CatalogModuleCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[ReferenceSQLInfo]:
    """Get reference SQL through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.get_reference_sql(request.subject_path)


@router.post(
    "/subject-tree/reference_sql/create",
    response_model=Result[dict],
    summary="Create Subject Reference SQL",
    description="Create reference SQL in the subject tree for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.reference_sql.create", resource_type="subject_tree")),
    ],
)
async def create_reference_sql(
    request: ReferenceSQLInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Create reference SQL through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.create_reference_sql(request)


@router.post(
    "/subject-tree/reference_sql/edit",
    response_model=Result[dict],
    summary="Edit Subject Reference SQL",
    description="Edit reference SQL in the subject tree for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.reference_sql.edit", resource_type="subject_tree")),
    ],
)
async def edit_reference_sql(
    request: ReferenceSQLInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Edit reference SQL through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.edit_reference_sql(request)


@router.post(
    "/subject-tree/semantic_model/edit",
    response_model=Result[dict],
    summary="Edit Subject Semantic Model Entry",
    description="Edit a semantic model entry for an authorized datasource",
    dependencies=[
        Depends(_require_config_edit),
        Depends(require_platform_active(operation="subject_tree.semantic_model.edit", resource_type="subject_tree")),
    ],
)
async def edit_semantic_model(
    request: EditSemanticModelInput,
    svc: ServiceDep,
    ctx: ConfigEditCtx,
    datasource_id: Optional[str] = DATASOURCE_QUERY,
) -> Result[dict]:
    """Edit a semantic model entry through request-scoped datasource projection."""
    explorer = await _project_explorer(svc, ctx, datasource_id=datasource_id)
    return await explorer.edit_semantic_model(request)

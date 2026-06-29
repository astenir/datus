"""
API routes for enterprise-safe subject tree discovery.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import project_request_config, require_module
from datus.api.models.base_models import Result
from datus.api.models.explorer_models import SubjectListData
from datus.api.services.explorer_service import ExplorerService
from datus.utils.exceptions import DatusException

router = APIRouter(prefix="/api/v1", tags=["subject"])
_require_catalog_module = require_module("module.datasource_catalog")
CatalogModuleCtx = Annotated[AppContext, Depends(_require_catalog_module)]

DATASOURCE_QUERY = Query("", description="Datasource to list subject tree from")


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
    try:
        projection = await project_request_config(
            ctx,
            svc.agent_config,
            operation="catalog.subject_tree",
            requested_datasource=datasource_id or None,
        )
    except DatusException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    explorer = ExplorerService(projection.config)
    return await explorer.get_subject_list()

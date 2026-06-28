"""API routes for knowledge base bootstrap with SSE streaming."""

import asyncio
import json
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import StreamingResponse

from datus.api import deps as api_deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_module, require_platform_active
from datus.api.models.base_models import Result
from datus.api.models.kb_models import BootstrapDocInput, BootstrapKbInput
from datus.api.utils.path_utils import safe_resolve
from datus.api.utils.stream_cancellation import (
    cancel_stream,
    cleanup_cancel_token,
    create_cancel_token,
)
from datus.utils.exceptions import DatusException

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge-base"])
_require_kb_module = require_module("module.kb")
KbModuleCtx = Annotated[AppContext, Depends(_require_kb_module)]
SSE_RESPONSE = {
    200: {
        "description": "Server-Sent Events progress stream",
        "content": {
            "text/event-stream": {
                "schema": {
                    "type": "string",
                    "description": "SSE frames encoded as id/event/data lines. See docs/API/knowledge_base.md.",
                }
            }
        },
    }
}


def _create_stream_cancel_token(ctx: AppContext) -> tuple[str, asyncio.Event]:
    for _ in range(3):
        stream_id = str(uuid.uuid4())
        try:
            cancel_event = create_cancel_token(stream_id, owner_user_id=ctx.user_id, project_id=ctx.project_id)
            return stream_id, cancel_event
        except ValueError:
            continue
    raise HTTPException(status_code=503, detail="STREAM_ID_COLLISION")


@router.post(
    "/bootstrap",
    summary="Bootstrap Knowledge Base",
    description="Start KB bootstrap with SSE progress streaming",
    response_class=StreamingResponse,
    responses=SSE_RESPONSE,
    dependencies=[
        Depends(_require_kb_module),
        Depends(require_platform_active(operation="kb.bootstrap", resource_type="kb")),
    ],
)
async def bootstrap_kb(
    request: BootstrapKbInput,
    _ctx: KbModuleCtx,
    http_request: Request,
):
    """Start KB bootstrap with SSE progress streaming."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    # Derive project_files_root from AgentConfig.home (= project dir)
    project_files_root = os.path.join(svc.agent_config.home, "files")

    # Validate user-supplied paths against the project root
    try:
        _validate_paths(request, project_files_root)
    except DatusException as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    stream_id, cancel_event = _create_stream_cancel_token(_ctx)

    async def generate_sse():
        try:
            async for event in svc.kb.bootstrap_stream(request, stream_id, cancel_event, project_files_root):
                data = json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False)
                yield f"id: {stream_id}\nevent: {event.stage}\ndata: {data}\n\n"
        finally:
            cleanup_cancel_token(stream_id)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post(
    "/bootstrap/{stream_id}/cancel",
    response_model=Result[dict],
    summary="Cancel Bootstrap",
    description="Cancel a running bootstrap stream",
    dependencies=[Depends(_require_kb_module)],
)
async def cancel_bootstrap(
    _ctx: KbModuleCtx,
    stream_id: str = Path(..., description="Stream ID to cancel"),
):
    """Cancel a running bootstrap stream."""
    cancelled = cancel_stream(stream_id, owner_user_id=_ctx.user_id, project_id=_ctx.project_id)
    return Result(success=cancelled, data={"stream_id": stream_id, "cancelled": cancelled})


def _validate_paths(request: BootstrapKbInput, project_root: str) -> None:
    """Validate that user-supplied file paths don't escape the project root."""
    from pathlib import Path as P

    base = P(project_root)
    if request.success_story:
        safe_resolve(base, request.success_story)
    if request.sql_dir:
        safe_resolve(base, request.sql_dir)


# ======================================================================
# Platform document bootstrap
# ======================================================================


@router.post(
    "/bootstrap-docs",
    summary="Bootstrap Platform Documentation",
    description="Start platform documentation bootstrap with SSE progress streaming",
    response_class=StreamingResponse,
    responses=SSE_RESPONSE,
    dependencies=[
        Depends(_require_kb_module),
        Depends(require_platform_active(operation="kb.bootstrap_docs", resource_type="kb")),
    ],
)
async def bootstrap_docs(
    request: BootstrapDocInput,
    _ctx: KbModuleCtx,
    http_request: Request,
):
    """Start platform doc bootstrap with SSE progress streaming."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    # Validate: platform must exist in config OR request must supply source
    platform = request.platform
    doc_cfg = svc.agent_config.document_configs.get(platform)
    if not doc_cfg and not request.source:
        raise HTTPException(
            status_code=422,
            detail=f"Platform '{platform}' not found in agent config and no source provided",
        )

    # Path validation for local sources
    source_type = request.source_type or (doc_cfg.type if doc_cfg else None)
    source = request.source or (doc_cfg.source if doc_cfg else None)
    if source and source_type == "local":
        from pathlib import Path as P

        project_files_root = os.path.join(svc.agent_config.home, "files")
        try:
            safe_resolve(P(project_files_root), source)
        except DatusException as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    stream_id, cancel_event = _create_stream_cancel_token(_ctx)

    async def generate_sse():
        try:
            async for event in svc.kb.bootstrap_doc_stream(request, stream_id, cancel_event):
                data = json.dumps(event.model_dump(exclude_none=True), ensure_ascii=False)
                yield f"id: {stream_id}\nevent: {event.stage}\ndata: {data}\n\n"
        finally:
            cleanup_cancel_token(stream_id)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post(
    "/bootstrap-docs/{stream_id}/cancel",
    response_model=Result[dict],
    summary="Cancel Doc Bootstrap",
    description="Cancel a running platform doc bootstrap stream",
    dependencies=[Depends(_require_kb_module)],
)
async def cancel_doc_bootstrap(
    _ctx: KbModuleCtx,
    stream_id: str = Path(..., description="Stream ID to cancel"),
):
    """Cancel a running platform doc bootstrap stream."""
    cancelled = cancel_stream(stream_id, owner_user_id=_ctx.user_id, project_id=_ctx.project_id)
    return Result(success=cancelled, data={"stream_id": stream_id, "cancelled": cancelled})

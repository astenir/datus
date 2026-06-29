"""API routes for knowledge base bootstrap with SSE streaming."""

import asyncio
import json
import os
import uuid
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile
from fastapi.responses import StreamingResponse

from datus.api import deps as api_deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import get_audit_sink, require_module, require_platform_active
from datus.api.enterprise.models import AuditEvent
from datus.api.models.base_models import Result
from datus.api.models.kb_models import (
    BootstrapDocInput,
    BootstrapKbInput,
    KbComponent,
    KbUploadDeleteResponse,
    KbUploadedFile,
    KbUploadPurpose,
    KbUploadRecord,
    KbUploadStatus,
)
from datus.api.services.kb_upload_store import KbUploadStore, make_kb_upload_store
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


# ======================================================================
# Browser upload staging
# ======================================================================


@router.post(
    "/uploads",
    response_model=KbUploadRecord,
    summary="Upload KB Source Files",
    description=(
        "Upload CSV, SQL, or text documentation files into the controlled project files area. "
        "Zip archives are not supported by this endpoint."
    ),
    dependencies=[
        Depends(_require_kb_module),
        Depends(require_platform_active(operation="kb.upload.create", resource_type="kb_upload")),
    ],
)
async def create_kb_upload(
    _ctx: KbModuleCtx,
    http_request: Request,
    purpose: Annotated[KbUploadPurpose, Form(description="Upload purpose for later KB bootstrap.")],
    files: Annotated[list[UploadFile], File(description="One or more KB source files.")],
    platform: Annotated[str | None, Form(description="Optional documentation platform name.")] = None,
    datasource_id: Annotated[str | None, Form(description="Optional datasource id associated with the upload.")] = None,
    description: Annotated[str | None, Form(description="Optional non-sensitive upload description.")] = None,
) -> KbUploadRecord:
    """Stage browser-uploaded source files for later KB bootstrap."""

    svc = await api_deps.resolve_datus_service_for_request(http_request)
    project_id = _project_id_for_request(svc, _ctx)
    record = await _upload_store_for_service(svc).create_upload(
        purpose=purpose,
        files=files,
        owner_user_id=_ctx.user_id,
        project_id=project_id,
        metadata=_upload_metadata(platform=platform, datasource_id=datasource_id, description=description),
    )
    await _audit_kb_event(
        _ctx,
        action="kb.upload.create",
        resource_id=record.upload_id,
        decision="allow",
        metadata={"purpose": record.purpose.value, "file_count": len(record.files), "project_id": project_id},
    )
    return record


@router.get(
    "/uploads/{upload_id}",
    response_model=KbUploadRecord,
    summary="Get KB Upload",
    description="Return KB upload metadata and file list. The caller must own the upload or be an administrator.",
    dependencies=[Depends(_require_kb_module)],
)
async def get_kb_upload(
    upload_id: str,
    _ctx: KbModuleCtx,
    http_request: Request,
) -> KbUploadRecord:
    """Return a staged KB upload."""

    svc = await api_deps.resolve_datus_service_for_request(http_request)
    record = _get_accessible_upload(_upload_store_for_service(svc), upload_id, _ctx, _project_id_for_request(svc, _ctx))
    await _audit_kb_event(
        _ctx,
        action="kb.upload.read",
        resource_id=upload_id,
        decision="allow",
        metadata={"purpose": record.purpose.value, "project_id": record.project_id},
    )
    return record


@router.delete(
    "/uploads/{upload_id}",
    response_model=KbUploadDeleteResponse,
    summary="Delete KB Upload",
    description="Delete staged KB upload files. The caller must own the upload or be an administrator.",
    dependencies=[
        Depends(_require_kb_module),
        Depends(require_platform_active(operation="kb.upload.delete", resource_type="kb_upload")),
    ],
)
async def delete_kb_upload(
    upload_id: str,
    _ctx: KbModuleCtx,
    http_request: Request,
) -> KbUploadDeleteResponse:
    """Delete a staged KB upload and its temporary files."""

    svc = await api_deps.resolve_datus_service_for_request(http_request)
    store = _upload_store_for_service(svc)
    record = _get_accessible_upload(store, upload_id, _ctx, _project_id_for_request(svc, _ctx))
    deleted = store.mark_deleted(upload_id) is not None
    await _audit_kb_event(
        _ctx,
        action="kb.upload.delete",
        resource_id=upload_id,
        decision="allow",
        metadata={"purpose": record.purpose.value, "project_id": record.project_id},
    )
    return KbUploadDeleteResponse(upload_id=upload_id, deleted=deleted)


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

    request = await _resolve_kb_upload_sources(
        request,
        store=_upload_store_for_service(svc),
        ctx=_ctx,
        project_id=_project_id_for_request(svc, _ctx),
        project_files_root=project_files_root,
    )

    # Validate user-supplied and upload-derived paths against the project files root.
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


async def _resolve_kb_upload_sources(
    request: BootstrapKbInput,
    *,
    store: KbUploadStore,
    ctx: AppContext,
    project_id: str,
    project_files_root: str,
) -> BootstrapKbInput:
    updates: dict[str, str] = {}
    upload_ids_for_audit: list[str] = []
    components = {
        component.value if hasattr(component, "value") else str(component) for component in request.components
    }

    needs_success_story = bool(components & {KbComponent.SEMANTIC_MODEL.value, KbComponent.METRICS.value})
    success_story_upload_id = request.success_story_upload_id
    if not success_story_upload_id and needs_success_story and request.upload_id:
        success_story_upload_id = request.upload_id
    if success_story_upload_id and not request.success_story:
        record = _get_available_upload_for_build(
            store,
            success_story_upload_id,
            ctx,
            project_id,
            expected_purpose=KbUploadPurpose.SUCCESS_STORY_CSV,
        )
        selected_file = _select_upload_file(record, request.success_story_file_id)
        updates["success_story"] = selected_file.relative_path
        upload_ids_for_audit.append(record.upload_id)

    reference_sql_upload_id = request.reference_sql_upload_id
    if not reference_sql_upload_id and KbComponent.REFERENCE_SQL.value in components and request.upload_id:
        reference_sql_upload_id = request.upload_id
    if reference_sql_upload_id and not request.sql_dir:
        record = _get_available_upload_for_build(
            store,
            reference_sql_upload_id,
            ctx,
            project_id,
            expected_purpose=KbUploadPurpose.REFERENCE_SQL,
        )
        updates["sql_dir"] = store.relative_upload_directory(record)
        upload_ids_for_audit.append(record.upload_id)

    if not updates:
        return request

    for relative_path in updates.values():
        safe_resolve(FilePath(project_files_root), relative_path)

    resolved_request = request.model_copy(update=updates)
    for upload_id in sorted(set(upload_ids_for_audit)):
        await _audit_kb_event(
            ctx,
            action="kb.bootstrap.from_upload",
            resource_id=upload_id,
            decision="allow",
            metadata={"components": [str(component) for component in request.components]},
        )
    return resolved_request


def _resolve_doc_upload_source(
    request: BootstrapDocInput,
    *,
    store: KbUploadStore,
    ctx: AppContext,
    project_id: str,
) -> BootstrapDocInput:
    if not request.upload_id:
        return request
    record = _get_available_upload_for_build(
        store,
        request.upload_id,
        ctx,
        project_id,
        expected_purpose=KbUploadPurpose.PLATFORM_DOCS,
    )
    return request.model_copy(update={"source_type": "local", "source": store.relative_upload_directory(record)})


def _select_upload_file(record: KbUploadRecord, file_id: str | None) -> KbUploadedFile:
    if file_id:
        for file in record.files:
            if file.file_id == file_id:
                return file
        raise HTTPException(status_code=404, detail="KB_UPLOAD_NOT_FOUND")
    if not record.files:
        raise HTTPException(status_code=422, detail="KB_UPLOAD_EMPTY")
    return record.files[0]


def _get_available_upload_for_build(
    store: KbUploadStore,
    upload_id: str,
    ctx: AppContext,
    project_id: str,
    *,
    expected_purpose: KbUploadPurpose,
) -> KbUploadRecord:
    record = _get_accessible_upload(store, upload_id, ctx, project_id)
    if record.status != KbUploadStatus.AVAILABLE:
        raise HTTPException(status_code=404, detail="KB_UPLOAD_NOT_FOUND")
    if record.purpose != expected_purpose:
        raise HTTPException(status_code=422, detail="KB_UPLOAD_INVALID_PURPOSE")
    return record


def _get_accessible_upload(store: KbUploadStore, upload_id: str, ctx: AppContext, project_id: str) -> KbUploadRecord:
    record = store.get_upload(upload_id)
    if record is None or record.status != KbUploadStatus.AVAILABLE:
        raise HTTPException(status_code=404, detail="KB_UPLOAD_NOT_FOUND")
    if record.project_id == project_id and record.owner_user_id == ctx.user_id:
        return record
    if ctx.is_admin:
        return record
    raise HTTPException(status_code=403, detail="KB_UPLOAD_FORBIDDEN")


def _upload_store_for_service(svc) -> KbUploadStore:
    return make_kb_upload_store(svc.agent_config)


def _project_id_for_request(svc, ctx: AppContext) -> str:
    raw_project = getattr(svc, "project_id", None)
    if isinstance(raw_project, str) and raw_project.strip():
        return raw_project.strip()
    if ctx.project_id:
        return ctx.project_id
    return "default"


def _upload_metadata(
    *,
    platform: str | None = None,
    datasource_id: str | None = None,
    description: str | None = None,
) -> dict[str, str]:
    metadata = {}
    for key, value in {
        "platform": platform,
        "datasource_id": datasource_id,
        "description": description,
    }.items():
        if value:
            metadata[key] = value
    return metadata


async def _audit_kb_event(
    ctx: AppContext,
    *,
    action: str,
    resource_id: str | None,
    decision: str,
    metadata: dict | None = None,
) -> None:
    try:
        await get_audit_sink().write(
            AuditEvent(
                user_id=ctx.user_id,
                action=action,
                resource_type="kb_upload",
                resource_id=resource_id,
                decision=decision,
                metadata=metadata or {},
            )
        )
    except Exception:
        return None


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
    if not doc_cfg and not request.source and not request.upload_id:
        raise HTTPException(
            status_code=422,
            detail=f"Platform '{platform}' not found in agent config and no source provided",
        )

    project_files_root = os.path.join(svc.agent_config.home, "files")
    if request.upload_id:
        request = _resolve_doc_upload_source(
            request,
            store=_upload_store_for_service(svc),
            ctx=_ctx,
            project_id=_project_id_for_request(svc, _ctx),
        )
        await _audit_kb_event(
            _ctx,
            action="kb.bootstrap.from_upload",
            resource_id=request.upload_id,
            decision="allow",
            metadata={"purpose": KbUploadPurpose.PLATFORM_DOCS.value, "component": "platform_docs"},
        )

    # Path validation for local sources
    source_type = request.source_type or (doc_cfg.type if doc_cfg else None)
    source = request.source or (doc_cfg.source if doc_cfg else None)
    if source and source_type == "local":
        from pathlib import Path as P

        try:
            resolved_source = safe_resolve(P(project_files_root), source)
        except DatusException as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        request = request.model_copy(update={"source_type": "local", "source": str(resolved_source)})

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

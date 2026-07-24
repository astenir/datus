"""API routes for saving trusted successful SQL executions as success stories."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from datus.api import deps as api_deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import (
    authorize_session_access,
    get_audit_sink,
    require_module,
    require_platform_active,
)
from datus.api.enterprise.models import AuditEvent
from datus.api.models.base_models import Result
from datus.api.models.success_story_models import SuccessStoryData, SuccessStoryInput
from datus.api.services.chat_service import SuccessStorySourceError
from datus.utils.constants import SQLType
from datus.utils.loggings import get_logger
from datus.utils.sql_utils import _first_statement, parse_sql_type, strip_sql_comments

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/success-stories", tags=["success-stories"])
_require_kb_module = require_module("module.kb")
KbModuleCtx = Annotated[AppContext, Depends(_require_kb_module)]
_READ_ONLY_SQL_TYPES = {SQLType.SELECT, SQLType.METADATA_SHOW, SQLType.EXPLAIN}


@router.post(
    "",
    summary="Save Success Story",
    description=(
        "Resolve a completed execute_sql/read_query call from canonical session history "
        "and idempotently save a read-only query as a success story."
    ),
    response_model=Result[SuccessStoryData],
    dependencies=[
        Depends(_require_kb_module),
        Depends(require_platform_active(operation="knowledge.success_story.save", resource_type="success_story")),
    ],
)
async def save_success_story(
    payload: SuccessStoryInput,
    request: Request,
    ctx: KbModuleCtx,
) -> Result[SuccessStoryData]:
    svc = await api_deps.resolve_datus_service_for_request(request)
    access = await authorize_session_access(
        svc,
        ctx,
        payload.session_id,
        action="success_story.save",
        require_existing_session=True,
    )
    if access.error is not None:
        code = (
            "SUCCESS_STORY_SESSION_FORBIDDEN"
            if access.error.errorCode == "SESSION_FORBIDDEN"
            else "SUCCESS_STORY_SOURCE_NOT_FOUND"
        )
        return _error(code, "The session is unavailable or cannot be accessed.")

    try:
        source = await svc.chat.resolve_success_story_source_async(
            payload.session_id,
            payload.call_tool_id,
            user_id=access.user_id,
            session_link=payload.session_link,
        )
    except SuccessStorySourceError as exc:
        return _error(exc.code, str(exc))

    normalized_sql = strip_sql_comments(source.sql).strip().rstrip(";").strip()
    statement_type = parse_sql_type(normalized_sql, "")
    if _first_statement(normalized_sql) != normalized_sql or statement_type not in _READ_ONLY_SQL_TYPES:
        await _audit_success_story(
            ctx,
            payload,
            decision="deny",
            reason="SQL statement is not read-only",
            metadata={"datasource_id": source.datasource_id, "statement_type": statement_type.value},
        )
        return _error(
            "SUCCESS_STORY_SQL_NOT_READ_ONLY",
            "Only read-only SELECT, SHOW, or EXPLAIN statements can be saved.",
        )

    try:
        data = svc.success_story.save(source)
    except OSError:
        logger.exception("Failed to write success story")
        await _audit_success_story(
            ctx,
            payload,
            decision="deny",
            reason="Success-story persistence failed",
            metadata={"datasource_id": source.datasource_id, "statement_type": statement_type.value},
        )
        return _error("SUCCESS_STORY_WRITE_FAILED", "The success story could not be saved. Please retry.")

    await _audit_success_story(
        ctx,
        payload,
        decision="allow",
        metadata={
            "datasource_id": source.datasource_id,
            "subagent_name": source.subagent_name,
            "storage_key": data.storage_key,
            "statement_type": statement_type.value,
            "sql_sha256": hashlib.sha256(source.sql.encode("utf-8")).hexdigest(),
            "created": data.created,
        },
    )
    return Result[SuccessStoryData](success=True, data=data)


def _error(code: str, message: str) -> Result[SuccessStoryData]:
    return Result[SuccessStoryData](success=False, errorCode=code, errorMessage=message)


async def _audit_success_story(
    ctx: AppContext,
    payload: SuccessStoryInput,
    *,
    decision: str,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        await get_audit_sink().write(
            AuditEvent(
                user_id=ctx.user_id,
                action="knowledge.success_story.save",
                resource_type="success_story",
                resource_id=payload.call_tool_id,
                decision=decision,
                reason=reason,
                metadata={
                    "session_id": payload.session_id,
                    "call_tool_id": payload.call_tool_id,
                    **(metadata or {}),
                },
            )
        )
    except Exception:
        logger.warning("Failed to write success-story audit event", exc_info=True)

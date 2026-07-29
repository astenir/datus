"""Enterprise policy checks used by chat request routes."""

from fnmatch import fnmatchcase
from typing import Any

from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_authorized_module
from datus.api.hooks import ChatPreCheckOutcome
from datus.api.models.downstream import StreamChatInput
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.model_policy import is_model_ref_allowed
from datus_enterprise.quota import consume_enterprise_quota
from datus_enterprise.services.sub_agent_task_policy import configure_enterprise_plan_mode_delegation

logger = get_logger(__name__)
_ELEVATED_PERMISSION_MODES = {"auto", "dangerous"}


def default_enterprise_chat_permission_mode(request: StreamChatInput, *, enterprise_enabled: bool) -> None:
    """Keep omitted enterprise permission modes on the least permissive profile."""

    if enterprise_enabled and request.permission_mode is None:
        request.permission_mode = "normal"


async def configure_chat_plan_mode_delegation(
    ctx: AppContext,
    request: StreamChatInput,
    *,
    agent_config: Any,
    parent_agent_record: dict[str, Any] | None,
    operation: str,
) -> ChatPreCheckOutcome | None:
    """Make ACL-visible Explore a request-scoped Plan Mode dependency."""
    missing_agent_ids = configure_enterprise_plan_mode_delegation(
        agent_config,
        plan_mode=bool(request.plan_mode),
    )
    denial: ChatPreCheckOutcome | None = None
    if missing_agent_ids:
        missing_names = ", ".join(sorted(missing_agent_ids))
        denial = ChatPreCheckOutcome(
            allow=False,
            error=(
                "Plan Mode requires the Explore Agent, but it is not published "
                f"or is not allowed by the Agent ACL: {missing_names}."
            ),
            error_type="PLAN_MODE_EXPLORE_FORBIDDEN",
        )
    elif request.plan_mode and _parent_policy_denies_task(parent_agent_record):
        agent_config._request_required_subagent_ids = set()
        denial = ChatPreCheckOutcome(
            allow=False,
            error="Plan Mode requires task delegation, but the selected Agent explicitly denies sub_agent_tools.task.",
            error_type="PLAN_MODE_DELEGATION_FORBIDDEN",
        )

    if denial is None:
        return None

    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="agent.dispatch",
                resource_type="agent",
                resource_id="explore",
                decision="deny",
                reason=denial.error_type,
                metadata={
                    "operation": operation,
                    "session_id": request.session_id,
                    "subagent_id": request.subagent_id,
                    "plan_mode": True,
                },
            ),
        )
    except Exception:
        logger.warning("Plan Mode Explore denial audit failed for operation=%s", operation, exc_info=True)
    return denial


def _parent_policy_denies_task(parent_agent_record: dict[str, Any] | None) -> bool:
    if not isinstance(parent_agent_record, dict):
        return False
    from datus_enterprise.agent_registry import agent_policy_metadata

    denied_patterns = agent_policy_metadata(parent_agent_record)["tool_policy"]["denied"]
    return any(fnmatchcase("sub_agent_tools.task", pattern) for pattern in denied_patterns)


async def authorize_chat_permission_mode(
    request: StreamChatInput,
    ctx: AppContext,
    *,
    enterprise_enabled: bool,
) -> None:
    """Require user RBAC before an enterprise request raises its tool profile."""

    if not enterprise_enabled or request.permission_mode not in _ELEVATED_PERMISSION_MODES:
        return
    try:
        await require_authorized_module(ctx, "module.chat.permission_mode")
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        raise HTTPException(
            status_code=403,
            detail=(f"Permission mode '{request.permission_mode}' requires module.chat.permission_mode."),
        ) from exc


async def audit_chat_sql_policy_denial(
    ctx: AppContext,
    request: StreamChatInput,
    denial: ChatPreCheckOutcome,
    *,
    operation: str,
) -> None:
    """Record a sanitized audit event for chat SQL-policy pre-check denial."""

    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="sql.policy.principal",
                resource_type="chat",
                resource_id=request.session_id,
                decision="deny",
                reason=denial.error_type or "SQL_POLICY_PRINCIPAL_REQUIRED",
                metadata={
                    "operation": operation,
                    "session_id": request.session_id,
                    "subagent_id": request.subagent_id,
                    "datasource": request.datasource,
                    "database": request.database,
                    "error_code": denial.error_type,
                    "missing_principal_paths": denial.extra.get("missing_principal_paths", []),
                },
            ),
        )
    except Exception:
        logger.warning("Chat SQL policy denial audit failed for operation=%s", operation, exc_info=True)


async def consume_chat_request_quota(
    ctx: AppContext,
    request: StreamChatInput,
    *,
    operation: str,
) -> ChatPreCheckOutcome | None:
    quota_error = await consume_enterprise_quota(
        ctx,
        resource=operation,
        amount=1,
        resource_type="chat",
        resource_id=request.session_id,
        metadata={
            "operation": operation,
            "session_id": request.session_id,
            "subagent_id": request.subagent_id,
            "datasource": request.datasource,
            "database": request.database,
            "model": request.model,
        },
    )
    if quota_error is None:
        return None
    return ChatPreCheckOutcome(
        allow=False,
        error=quota_error.errorMessage or "Quota exceeded.",
        error_type=quota_error.errorCode or "QUOTA_DENIED",
    )


async def enforce_chat_model_policy(
    ctx: AppContext,
    request: StreamChatInput,
    *,
    agent_config: Any,
    operation: str,
) -> ChatPreCheckOutcome | None:
    model_ref = request.model or _active_model_ref(agent_config)
    if is_model_ref_allowed(ctx, model_ref):
        return None

    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action="model.select",
                resource_type="model",
                resource_id=model_ref,
                decision="deny",
                reason="MODEL_FORBIDDEN",
                metadata={
                    "operation": operation,
                    "session_id": request.session_id,
                    "subagent_id": request.subagent_id,
                    "requested_model": request.model,
                },
            ),
        )
    except Exception:
        logger.warning("Chat model policy denial audit failed for operation=%s", operation, exc_info=True)
    return ChatPreCheckOutcome(
        allow=False,
        error=f"Model '{model_ref}' is not authorized for this request.",
        error_type="MODEL_FORBIDDEN",
    )


def _active_model_ref(agent_config: Any) -> str | None:
    provider = getattr(agent_config, "_target_provider", None)
    model = getattr(agent_config, "_target_model", None)
    if isinstance(provider, str) and provider and isinstance(model, str) and model:
        return f"{provider}/{model}"

    target = getattr(agent_config, "target", None)
    custom_models = getattr(agent_config, "models", None)
    if isinstance(target, str) and target and isinstance(custom_models, dict) and target in custom_models:
        return f"custom/{target}"

    return None

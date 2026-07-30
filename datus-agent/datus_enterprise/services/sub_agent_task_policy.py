"""Enterprise policy helpers for delegated Agent execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from datus.tools.func_tool.base import FuncToolResult
from datus.utils.constants import HIDDEN_SYS_SUB_AGENTS, SYS_SUB_AGENTS
from datus.utils.loggings import get_logger

if TYPE_CHECKING:
    from datus.agent.node.agentic_node import AgenticNode
    from datus.configuration.agent_config import AgentConfig

logger = get_logger(__name__)
_MISSING_AGENT_ID = object()

# ``explore`` is a first-class upstream task() target but intentionally does
# not live in SYS_SUB_AGENTS. Keep enterprise registration and task discovery
# on one downstream-owned definition so built-ins cannot silently drift out
# of Agent ACL governance.
ENTERPRISE_DELEGATABLE_BUILTIN_AGENT_IDS = frozenset((SYS_SUB_AGENTS - HIDDEN_SYS_SUB_AGENTS) | {"explore"})
ENTERPRISE_PLAN_MODE_REQUIRED_AGENT_IDS = frozenset({"explore"})


def configure_enterprise_plan_mode_delegation(
    agent_config: "AgentConfig",
    *,
    plan_mode: bool,
) -> set[str]:
    """Enable Plan Mode's required delegation on the request-scoped config.

    The required target must already be visible through the effective
    enterprise Agent ACL. This only removes duplication with the parent
    Agent's general delegation policy; it never grants access to the target.
    """
    required_agent_ids: set[str] = set()
    if bool(getattr(agent_config, "_enterprise_enabled", False)) and plan_mode:
        required_agent_ids.update(ENTERPRISE_PLAN_MODE_REQUIRED_AGENT_IDS)

    allowed_agent_ids = set(getattr(agent_config, "_enterprise_allowed_agent_ids", set()) or set())
    missing_agent_ids = required_agent_ids - allowed_agent_ids
    agent_config._request_required_subagent_ids = set() if missing_agent_ids else required_agent_ids
    return missing_agent_ids


def inherit_parent_permission_profile(
    *,
    parent_node: Any,
    agent_config: "AgentConfig",
    node: "AgenticNode",
) -> None:
    """Apply the request-scoped parent profile to a delegated node.

    API chat changes the freshly-created parent's PermissionManager without
    mutating shared AgentConfig. Delegated nodes are created later from that
    unchanged config, so they must inherit the effective profile explicitly
    while retaining their node overrides and tool policy.
    """
    parent_manager = getattr(parent_node, "permission_manager", None)
    target_profile = getattr(parent_manager, "active_profile", None)
    if not isinstance(target_profile, str):
        return

    from datus.tools.permission.profiles import PROFILE_NAMES, build_user_overrides

    if target_profile not in PROFILE_NAMES:
        raise RuntimeError(f"Cannot delegate with unknown permission profile {target_profile!r}.")

    child_manager = getattr(node, "permission_manager", None)
    if child_manager is None or getattr(child_manager, "active_profile", None) == target_profile:
        return

    raw_permissions = getattr(agent_config, "_raw_permissions", {}) or {}
    if not isinstance(raw_permissions, dict):
        raise RuntimeError("Cannot inherit permission profile: agent permission configuration is malformed.")
    raw_user = {key: value for key, value in raw_permissions.items() if key != "profile"}

    try:
        user_overrides = build_user_overrides(target_profile, raw_user)
        child_manager.switch_profile(target_profile, user_overrides=user_overrides)
    except Exception as exc:
        raise RuntimeError(f"Failed to inherit permission profile {target_profile!r} for delegated Agent.") from exc

    logger.info(
        "Inherited permission profile for delegated Agent",
        profile=target_profile,
        parent=getattr(parent_node, "node_name", None),
        child=getattr(node, "node_name", None),
    )


def apply_delegated_agent_policy(
    *,
    parent_node: Any,
    agent_config: "AgentConfig",
    node: "AgenticNode",
) -> None:
    """Apply request scope and policy before delegated Agent execution."""
    parent_scope = getattr(parent_node, "scope", None)
    if isinstance(parent_scope, str) and parent_scope and not getattr(node, "scope", None):
        node.scope = parent_scope

    inherit_parent_permission_profile(
        parent_node=parent_node,
        agent_config=agent_config,
        node=node,
    )

    from datus.agent.tool_policy import apply_agent_runtime_policy

    apply_agent_runtime_policy(node)


def enterprise_agent_acl_denial(
    agent_config: "AgentConfig",
    subagent_type: str,
) -> Optional[FuncToolResult]:
    """Return a fail-closed denial when the effective Agent ACL rejects task()."""
    if not bool(getattr(agent_config, "_enterprise_enabled", False)):
        return None

    allowed_agent_ids = set(getattr(agent_config, "_enterprise_allowed_agent_ids", set()) or set())
    if subagent_type in allowed_agent_ids:
        return None

    logger.warning(
        "Enterprise task dispatch denied by Agent ACL: subagent=%s user=%r",
        subagent_type,
        getattr(agent_config, "_request_user_id", None),
    )
    return FuncToolResult(
        success=0,
        error=f"AGENT_FORBIDDEN: task(type={subagent_type!r}) is not allowed by the Agent ACL.",
    )


def enterprise_agent_acl_allows(
    agent_config: "AgentConfig",
    agent_name: str,
    *,
    entry_id: Any = _MISSING_AGENT_ID,
) -> bool:
    """Return whether discovery may expose an Agent under the effective ACL."""
    if not bool(getattr(agent_config, "_enterprise_enabled", False)):
        return True

    allowed_agent_ids = set(getattr(agent_config, "_enterprise_allowed_agent_ids", set()) or set())
    return agent_name in allowed_agent_ids or entry_id in allowed_agent_ids

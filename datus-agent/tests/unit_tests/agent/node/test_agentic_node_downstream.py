"""Downstream enterprise boundaries for the AgenticNode base class."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from datus.models.session_manager import session_scope_from_user_id
from datus.schemas.action_history import ActionHistoryManager, ActionRole, ActionStatus
from tests.unit_tests.agent.node.test_agentic_node import (
    TestEnsurePermissionHooksProxyWiring as _PermissionHooksFixture,
)
from tests.unit_tests.agent.node.test_agentic_node import _make_node, _make_simple_node


def test_drain_emits_one_failed_mcp_action_and_clears_pending_failures():
    node = _make_node()
    manager = ActionHistoryManager()

    node._record_mcp_connection_failure("filesystem", "connection refused")
    node._record_mcp_connection_failure("filesystem", "connection refused")
    actions = node._drain_mcp_connection_failure_actions(manager)

    assert len(actions) == 1
    action = actions[0]
    assert action.role == ActionRole.TOOL
    assert action.action_type == "mcp.filesystem.connect"
    assert action.status == ActionStatus.FAILED
    assert action.input == {"server_name": "filesystem"}
    assert action.output == {
        "error": "connection refused",
        "summary": "MCP Server 'filesystem' connection failed; the Agent continued without it.",
    }
    assert manager.get_actions() == actions
    assert node._drain_mcp_connection_failure_actions(manager) == []


def test_request_workspace_overrides_node_and_project_roots_for_opted_in_node():
    node = _make_node()
    node.USE_REQUEST_WORKSPACE = True
    node.node_config = {"workspace_root": "/configured/node/root"}
    config = MagicMock(spec=["project_root", "_request_workspace_root"])
    config.project_root = "/project/root"
    config._request_workspace_root = "/private/alice"
    node.agent_config = config

    assert node._resolve_workspace_root() == "/private/alice"


def test_project_authoring_node_ignores_request_workspace():
    node = _make_node()
    node.USE_REQUEST_WORKSPACE = False
    node.node_config = {}
    config = MagicMock(spec=["project_root", "_request_workspace_root"])
    config.project_root = "/project/root"
    config._request_workspace_root = "/private/alice"
    node.agent_config = config

    assert node._resolve_workspace_root() == "/project/root"


def test_session_manager_body_store_subagent_scope_includes_parent_session(tmp_path):
    body_store = object()
    agent_config = SimpleNamespace(
        session_dir=str(tmp_path / "sessions"),
        _session_body_store=body_store,
        _session_project_id="enterprise",
    )
    node = _make_node(
        agent_config=agent_config,
        scope="alice",
        session_subdir="chat.session_parent",
    )

    session_manager = node.session_manager

    assert session_manager._body_store is body_store
    assert session_manager.project_id == "enterprise"
    assert session_manager._scope == f"alice__{session_scope_from_user_id('chat.session_parent')}"


def test_enterprise_tool_and_runtime_policies_are_extracted():
    node = _make_simple_node()
    config = MagicMock()
    config.agentic_nodes = {
        "chat": {
            "tool_policy": {
                "mode": "allowlist",
                "allowed": ["db_tools.*"],
                "denied": ["filesystem_tools.*"],
            },
            "runtime_policy": {
                "allow_subagent_delegation": False,
                "allowed_subagents": [],
            },
        }
    }

    result = node._parse_node_config(config, "chat")

    assert result["tool_policy"] == config.agentic_nodes["chat"]["tool_policy"]
    assert result["runtime_policy"] == config.agentic_nodes["chat"]["runtime_policy"]


def test_permission_hooks_receive_canonical_node_class():
    node = _PermissionHooksFixture()._prepare_node(set())
    node.get_node_name = MagicMock(return_value="dashboard_edit__unit")
    node.get_node_class_name = MagicMock(return_value="gen_visual_dashboard")

    with patch("datus.tools.permission.permission_hooks.PermissionHooks") as hooks_class:
        node._ensure_permission_hooks()

    kwargs = hooks_class.call_args.kwargs
    assert kwargs["node_name"] == "dashboard_edit__unit"
    assert kwargs["node_class"] == "gen_visual_dashboard"

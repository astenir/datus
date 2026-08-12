"""Downstream enterprise boundaries for the AgenticNode base class."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from datus.models.session_manager import session_scope_from_user_id
from datus.schemas.action_history import ActionHistory, ActionHistoryManager, ActionRole, ActionStatus
from tests.unit_tests.agent.node.test_agentic_node import (
    TestEnsurePermissionHooksProxyWiring as _PermissionHooksFixture,
)
from tests.unit_tests.agent.node.test_agentic_node import _make_node, _make_simple_node


def test_drain_emits_a_failed_mcp_action_pair_and_clears_pending_failures():
    node = _make_node()
    manager = ActionHistoryManager()

    node._record_mcp_connection_failure("filesystem", "connection refused")
    node._record_mcp_connection_failure("filesystem", "connection refused")
    actions = node._drain_mcp_connection_failure_actions(manager)

    assert len(actions) == 2
    start_action, action = actions
    assert start_action.role == ActionRole.TOOL
    assert start_action.action_type == "mcp.filesystem.connect"
    assert start_action.status == ActionStatus.PROCESSING
    assert start_action.input == {
        "function_name": "mcp.filesystem.connect",
        "arguments": {},
        "server_name": "filesystem",
    }
    assert action.role == ActionRole.TOOL
    assert action.action_type == "mcp.filesystem.connect"
    assert action.action_id == f"complete_{start_action.action_id}"
    assert action.status == ActionStatus.FAILED
    assert action.input == start_action.input
    assert action.output == {
        "error": "Failed to connect to MCP server. Please check the server address and network connectivity.",
        "summary": "MCP Server 'filesystem' connection failed; the Agent continued without it.",
    }
    assert manager.get_actions() == actions
    assert node._drain_mcp_connection_failure_actions(manager) == []


def test_drain_resolves_personal_mcp_alias_to_display_name_in_summary():
    node = _make_node(
        agent_config=SimpleNamespace(
            _request_mcp_display_names={
                f"personal_{'a' * 32}": "我的搜索服务",
            }
        ),
    )
    manager = ActionHistoryManager()

    node._record_mcp_connection_failure(f"personal_{'a' * 32}", "connection refused")
    actions = node._drain_mcp_connection_failure_actions(manager)

    assert len(actions) == 2
    start_action, action = actions
    # The technical identity keeps the runtime alias; only the user-facing
    # summary resolves it back to the display name (MCP 名称).
    assert start_action.action_type == f"mcp.personal_{'a' * 32}.connect"
    assert start_action.input["server_name"] == f"personal_{'a' * 32}"
    assert action.output == {
        "error": "Failed to connect to MCP server. Please check the server address and network connectivity.",
        "summary": "MCP Server '我的搜索服务' connection failed; the Agent continued without it.",
    }


def test_drain_keeps_raw_alias_when_display_name_is_unknown():
    node = _make_node(agent_config=SimpleNamespace(_request_mcp_display_names={}))
    manager = ActionHistoryManager()

    node._record_mcp_connection_failure(f"personal_{'b' * 32}", "timed out")
    actions = node._drain_mcp_connection_failure_actions(manager)

    assert actions[1].output["summary"] == (
        f"MCP Server 'personal_{'b' * 32}' connection failed; the Agent continued without it."
    )


@pytest.mark.asyncio
async def test_mcp_failure_is_emitted_before_the_model_yields_its_first_action():
    node = _make_node()
    node.max_turns = 1
    node.mcp_servers = {"filesystem": object()}
    node._ensure_tool_transformers = lambda: None
    node._compose_run_hooks = lambda _ctx: None
    release_model = asyncio.Event()

    async def model_stream(**kwargs):
        kwargs["mcp_connection_failure_callback"](
            "filesystem",
            "MCP server returned HTTP 410.",
        )
        await release_model.wait()
        yield ActionHistory(
            action_id="model-action",
            role=ActionRole.ASSISTANT,
            action_type="response",
            messages="ready",
            input={},
            output={"content": "ready"},
            status=ActionStatus.SUCCESS,
        )

    node._pinned_model = MagicMock()
    node._pinned_model.generate_with_tools_stream = model_stream
    ctx = SimpleNamespace(
        user_input=SimpleNamespace(model_fields_set=set()),
        user_prompt="hello",
        system_instruction="",
        session=None,
        action_history_manager=ActionHistoryManager(),
        pending_input_queue=None,
    )

    stream = node._stream_once(ctx)
    first = await asyncio.wait_for(anext(stream), timeout=0.5)
    assert first.action_type == "mcp.filesystem.connect"
    assert first.status == ActionStatus.PROCESSING

    second = await asyncio.wait_for(anext(stream), timeout=0.5)
    assert second.action_id == f"complete_{first.action_id}"
    assert second.status == ActionStatus.FAILED

    release_model.set()
    remaining = [action async for action in stream]
    assert remaining[0].action_id == "model-action"


@pytest.mark.asyncio
async def test_closing_mcp_stream_cancels_the_blocked_model_connection_wait():
    node = _make_node()
    node.max_turns = 1
    node.mcp_servers = {"filesystem": object()}
    node._ensure_tool_transformers = lambda: None
    node._compose_run_hooks = lambda _ctx: None
    model_closed = asyncio.Event()

    async def model_stream(**kwargs):
        kwargs["mcp_connection_failure_callback"]("filesystem", "connection refused")
        try:
            await asyncio.Event().wait()
            yield ActionHistory(
                action_id="unreachable-model-action",
                role=ActionRole.ASSISTANT,
                action_type="response",
                messages="unreachable",
                input={},
                output={"content": "unreachable"},
                status=ActionStatus.SUCCESS,
            )
        finally:
            model_closed.set()

    node._pinned_model = MagicMock()
    node._pinned_model.generate_with_tools_stream = model_stream
    ctx = SimpleNamespace(
        user_input=SimpleNamespace(model_fields_set=set()),
        user_prompt="hello",
        system_instruction="",
        session=None,
        action_history_manager=ActionHistoryManager(),
        pending_input_queue=None,
    )

    stream = node._stream_once(ctx)
    await anext(stream)
    await anext(stream)
    await asyncio.wait_for(stream.aclose(), timeout=0.5)

    assert model_closed.is_set()
    assert node._mcp_connection_failure_event is None


@pytest.mark.asyncio
async def test_closing_after_a_model_action_keeps_mcp_cleanup_in_the_owner_task():
    node = _make_node()
    node.max_turns = 1
    node.mcp_servers = {"filesystem": object()}
    node._ensure_tool_transformers = lambda: None
    node._compose_run_hooks = lambda _ctx: None
    model_closed = asyncio.Event()

    class TaskAffinityContext:
        async def __aenter__(self):
            self.owner = asyncio.current_task()
            return self

        async def __aexit__(self, *_args):
            if asyncio.current_task() is not self.owner:
                raise RuntimeError("MCP cleanup crossed asyncio tasks")
            model_closed.set()
            return False

    async def model_stream(**kwargs):
        async with TaskAffinityContext():
            kwargs["mcp_connection_failure_callback"]("filesystem", "connection refused")
            yield ActionHistory(
                action_id="model-action",
                role=ActionRole.ASSISTANT,
                action_type="response",
                messages="ready",
                input={},
                output={"content": "ready"},
                status=ActionStatus.SUCCESS,
            )
            await asyncio.Event().wait()

    node._pinned_model = MagicMock()
    node._pinned_model.generate_with_tools_stream = model_stream
    ctx = SimpleNamespace(
        user_input=SimpleNamespace(model_fields_set=set()),
        user_prompt="hello",
        system_instruction="",
        session=None,
        action_history_manager=ActionHistoryManager(),
        pending_input_queue=None,
    )

    stream = node._stream_once(ctx)
    await anext(stream)
    await anext(stream)
    assert (await anext(stream)).action_id == "model-action"
    await asyncio.wait_for(stream.aclose(), timeout=0.5)

    assert model_closed.is_set()
    assert node._mcp_connection_failure_event is None


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


def test_enterprise_permission_hooks_receive_business_datasource_read_only_ceiling():
    node = _PermissionHooksFixture()._prepare_node(set())
    node.agent_config = SimpleNamespace(_enterprise_enabled=True)

    with patch("datus.tools.permission.permission_hooks.PermissionHooks") as hooks_class:
        node._ensure_permission_hooks()

    assert hooks_class.call_args.kwargs["business_datasource_read_only"] is True

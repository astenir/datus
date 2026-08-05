# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream chat-agent regressions."""

import pytest
from agents.exceptions import UserError

from datus.agent.node.chat_agentic_node import ChatAgenticNode
from datus.configuration.node_type import NodeType
from datus.schemas.action_history import ActionHistory, ActionHistoryManager, ActionRole, ActionStatus
from datus.schemas.chat_agentic_node_models import ChatNodeInput
from datus.tools.permission.permission_hooks import PermissionDeniedException


class ServiceUnavailableError(Exception):
    """Stand-in matching LiteLLM's stable exception class name."""


def _node(real_agent_config, *, node_id: str, description: str, node_name: str | None = None):
    kwargs = {}
    if node_name is not None:
        kwargs["node_name"] = node_name
    return ChatAgenticNode(
        node_id=node_id,
        description=description,
        node_type=NodeType.TYPE_CHAT,
        agent_config=real_agent_config,
        **kwargs,
    )


def test_enterprise_request_workspace_overrides_node_workspace(real_agent_config, mock_llm_create, tmp_path):
    request_workspace = tmp_path / "private" / "alice"
    request_workspace.mkdir(parents=True)
    previous_nodes = real_agent_config.agentic_nodes
    previous_request_workspace = getattr(real_agent_config, "_request_workspace_root", None)
    real_agent_config.agentic_nodes = {"chat": {"workspace_root": str(tmp_path / "shared")}}
    real_agent_config._request_workspace_root = str(request_workspace)
    try:
        node = _node(
            real_agent_config,
            node_id="test_request_workspace",
            description="Test request workspace",
        )
        assert node.filesystem_func_tool.root_path == str(request_workspace)
    finally:
        real_agent_config.agentic_nodes = previous_nodes
        if previous_request_workspace is None:
            del real_agent_config._request_workspace_root
        else:
            real_agent_config._request_workspace_root = previous_request_workspace


def test_missing_mcp_server_records_degraded_capability(real_agent_config, mock_llm_create):
    node = _node(real_agent_config, node_id="test_mcp_unknown", description="Test unknown MCP server")

    result = node._setup_mcp_server_from_config("non_existent_server_xyz")

    assert result is None
    assert "missing from the runtime configuration" in node.degraded_capabilities["mcp.non_existent_server_xyz"]


def test_custom_agent_renders_request_scoped_prompt_content(real_agent_config, mock_llm_create, caplog):
    real_agent_config.agentic_nodes["chat_custom"] = {
        "node_class": "chat",
        "system_prompt": "chat_custom",
        "prompt_template": "Custom database prompt for {{ agent_description }}.",
        "prompt_version": "1.0",
        "agent_description": "investment research",
        "tools": "",
    }
    node = _node(
        real_agent_config,
        node_id="test_custom_prompt",
        description="Test custom Agent prompt",
        node_name="chat_custom",
    )

    with caplog.at_level("WARNING"):
        prompt = node._get_system_prompt()

    assert "Custom database prompt for investment research." in prompt
    assert "Failed to render system prompt 'chat_custom'" not in caplog.text


def test_disabled_delegation_removes_task_and_prompt_guidance(real_agent_config, mock_llm_create):
    from datus.agent.tool_policy import apply_agent_runtime_policy
    from datus.tools.permission.permission_config import PermissionLevel

    chat_config = dict(real_agent_config.agentic_nodes.get("chat", {}))
    chat_config.update(
        {
            "tool_policy": {"mode": "inherit", "allowed": [], "denied": []},
            "runtime_policy": {"allow_subagent_delegation": False, "allowed_subagents": []},
        }
    )
    real_agent_config.agentic_nodes["chat"] = chat_config
    node = _node(real_agent_config, node_id="test_disabled_delegation", description="Test delegation policy")

    apply_agent_runtime_policy(node)

    assert node.node_config["runtime_policy"]["allow_subagent_delegation"] is False
    assert "task" not in {tool.name for tool in node.tools}
    assert node.sub_agent_task_tool._get_available_types() == []
    assert node.permission_manager.check_permission("sub_agent_tools", "task", "chat") == PermissionLevel.DENY
    assert "Task delegation tool (`task`)" not in node._get_system_prompt()


@pytest.mark.asyncio
async def test_execute_stream_applies_tool_policy_before_prompt_assembly(
    real_agent_config,
    mock_llm_create,
    monkeypatch,
):
    """An allowlist-pruned tool must not remain advertised in the same run."""
    chat_config = dict(real_agent_config.agentic_nodes.get("chat", {}))
    chat_config["tool_policy"] = {
        "mode": "allowlist",
        "allowed": ["db_tools.*"],
        "denied": [],
    }
    real_agent_config.agentic_nodes["chat"] = chat_config
    node = _node(real_agent_config, node_id="test_policy_before_prompt", description="Test prompt policy order")
    assert "ask_user" in {tool.name for tool in node.tools}

    observed = {}

    async def capture_stream(ctx):
        observed["tool_names"] = {tool.name for tool in node.tools}
        observed["system_instruction"] = ctx.system_instruction
        if False:  # pragma: no cover - keep this test double an async generator
            yield None

    monkeypatch.setattr(node, "_stream_once", capture_stream)
    node.input = ChatNodeInput(user_message="Analyze sales", database="california_schools")

    actions = [action async for action in node.execute_stream(ActionHistoryManager())]

    assert actions[-1].status == ActionStatus.SUCCESS
    assert "ask_user" not in observed["tool_names"]
    assert observed["tool_names"]
    assert all(node.tool_registry.get(name) == "db_tools" for name in observed["tool_names"])
    assert "Ask user tool (`ask_user`)" not in observed["system_instruction"]
    assert "No ask_user tool is available" in observed["system_instruction"]


@pytest.mark.asyncio
async def test_execute_stream_formats_permission_denial_as_user_message(real_agent_config, mock_llm_create):
    node = _node(real_agent_config, node_id="test_permission_denied", description="Test permission denial")
    original_method = mock_llm_create.generate_with_tools_stream

    async def raising_stream(*args, **kwargs):
        denied = PermissionDeniedException(
            "PERMISSION_DENIED: Tool 'write_file' (filesystem_tools) is blocked by the "
            "'normal' permission profile. STOP retrying this tool — different parameters "
            "will not change the outcome.",
            tool_category="filesystem_tools",
            tool_name="write_file",
        )
        raise UserError(f"Error running tool write_file: {denied}") from denied
        yield  # pragma: no cover

    mock_llm_create.generate_with_tools_stream = raising_stream
    node.input = ChatNodeInput(user_message="Create a file", database="california_schools")
    try:
        actions = [action async for action in node.execute_stream(ActionHistoryManager())]
        final_action = actions[-1]
        assert final_action.status == ActionStatus.FAILED
        assert final_action.output.get("error_type") == "PERMISSION_DENIED"
        error_text = str(final_action.output.get("error", ""))
        assert "权限受限" in error_text
        assert "当前 Agent 或会话的工具策略不允许直接修改文件" in error_text
        assert "核对该 Agent 的工具策略" in error_text
        assert "最高权限模式" not in error_text
        assert "授予“高危对话模式”权限" not in error_text
        assert "STOP retrying" not in error_text
        assert "permissions.rules" not in error_text
    finally:
        mock_llm_create.generate_with_tools_stream = original_method


@pytest.mark.asyncio
async def test_execute_stream_preserves_safe_upstream_unavailable_type(real_agent_config, mock_llm_create):
    node = _node(real_agent_config, node_id="test_upstream_unavailable", description="Test upstream failure")
    original_method = mock_llm_create.generate_with_tools_stream

    async def raising_stream(*args, **kwargs):
        raise ServiceUnavailableError(
            'litellm.ServiceUnavailableError: DeepseekException - {"error":{"message":"Service is too busy."}}'
        )
        yield  # pragma: no cover

    mock_llm_create.generate_with_tools_stream = raising_stream
    node.input = ChatNodeInput(user_message="Analyze sales", database="california_schools")
    try:
        actions = [action async for action in node.execute_stream(ActionHistoryManager())]
        final_action = actions[-1]
        assert final_action.status == ActionStatus.FAILED
        assert final_action.output.get("error_type") == "UPSTREAM_UNAVAILABLE"
        assert final_action.output.get("error") == "Service is too busy."
        assert "litellm" not in str(final_action.output)
        assert "DeepseekException" not in str(final_action.output)
    finally:
        mock_llm_create.generate_with_tools_stream = original_method


@pytest.mark.asyncio
async def test_execute_stream_preserves_usage_after_permission_denial(real_agent_config, mock_llm_create):
    node = _node(real_agent_config, node_id="test_permission_denied_usage", description="Test denial usage")
    original_method = mock_llm_create.generate_with_tools_stream

    async def raising_stream(*args, **kwargs):
        kwargs["action_history_manager"].add_action(
            ActionHistory(
                action_id="token_usage_before_denial",
                role=ActionRole.ASSISTANT,
                messages="Token usage update",
                action_type="token_usage",
                input={},
                output={
                    "cumulative": {
                        "requests": 1,
                        "input_tokens": 1200,
                        "output_tokens": 80,
                        "total_tokens": 1280,
                        "cached_tokens": 256,
                    },
                    "delta": {"requests": 1, "input_tokens": 1200, "output_tokens": 80, "total_tokens": 1280},
                    "context_length": 128000,
                    "last_call_input_tokens": 1200,
                },
                status=ActionStatus.SUCCESS,
            )
        )
        denied = PermissionDeniedException(
            "PERMISSION_DENIED: Tool 'write_file' (filesystem_tools) is blocked by the 'normal' permission profile.",
            tool_category="filesystem_tools",
            tool_name="write_file",
        )
        raise UserError(f"Error running tool write_file: {denied}") from denied
        yield  # pragma: no cover

    mock_llm_create.generate_with_tools_stream = raising_stream
    node.input = ChatNodeInput(user_message="Create a file", database="california_schools")
    try:
        actions = [action async for action in node.execute_stream(ActionHistoryManager())]
        final_action = actions[-1]
        assert final_action.status == ActionStatus.FAILED
        assert final_action.output.get("tokens_used") == 1280
        turn_usage = await node.get_last_turn_usage()
        assert turn_usage is not None
        assert turn_usage.total_tokens == 1280
        assert turn_usage.cached_tokens == 256
        assert turn_usage.session_total_tokens == 1200
    finally:
        mock_llm_create.generate_with_tools_stream = original_method

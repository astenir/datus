"""CI-level tests for SubAgentTaskTool (AgenticNode-based execution)."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from datus.configuration.agent_config import AgentConfig
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.tools.func_tool.sub_agent_task_tool import SubAgentTaskTool
from datus_enterprise.services.sub_agent_task_policy import (
    enterprise_agent_acl_denial,
    inherit_parent_permission_profile,
)


@pytest.fixture
def mock_agent_config():
    config = Mock(spec=AgentConfig)
    config.db_type = "sqlite"
    config.current_datasource = "test_db"
    config.agentic_nodes = {
        "chat": {"model": "default"},
        "gen_sql": {"model": "default", "system_prompt": "gen_sql", "node_class": "gen_sql"},
        "sales_analyst": {"model": "default", "node_class": "gen_sql", "agent_description": "Sales data specialist"},
    }
    config.sub_agent_config.side_effect = lambda name: config.agentic_nodes.get(name)
    return config


@pytest.fixture
def task_tool(mock_agent_config):
    return SubAgentTaskTool(agent_config=mock_agent_config)


@pytest.mark.ci
class TestPermissionProfileInheritance:
    @pytest.mark.parametrize(
        ("parent_profile", "child_profile"), [("auto", "normal"), ("dangerous", "normal"), ("normal", "dangerous")]
    )
    def test_delegated_node_inherits_parent_request_profile_without_mutating_config(
        self, mock_agent_config, parent_profile, child_profile
    ):
        from datus.tools.permission.permission_config import PermissionLevel
        from datus.tools.permission.permission_manager import PermissionManager
        from datus.tools.permission.profiles import get_profile

        mock_agent_config.active_profile_name = child_profile
        mock_agent_config._raw_permissions = {
            "profile": child_profile,
            "rules": [{"tool": "db_tools", "pattern": "blocked_by_admin", "permission": "deny"}],
        }
        parent = MagicMock()
        parent.permission_manager = PermissionManager(
            global_config=get_profile(parent_profile), active_profile=parent_profile
        )
        child_manager = PermissionManager(
            global_config=get_profile(child_profile),
            node_overrides={
                "ask_metrics": {
                    "rules": [{"tool": "semantic_tools", "pattern": "private_metric", "permission": "deny"}]
                }
            },
            active_profile=child_profile,
        )
        child = MagicMock()
        child.permission_manager = child_manager
        inherit_parent_permission_profile(
            parent_node=parent,
            agent_config=mock_agent_config,
            node=child,
        )
        assert child_manager.active_profile == parent_profile
        assert child_manager.check_permission("db_tools", "blocked_by_admin", "ask_metrics") == PermissionLevel.DENY
        assert child_manager.check_permission("semantic_tools", "private_metric", "ask_metrics") == PermissionLevel.DENY
        assert mock_agent_config.active_profile_name == child_profile

    def test_profile_inheritance_failure_stops_delegated_node(self, mock_agent_config):
        from datus.tools.permission.permission_manager import PermissionManager
        from datus.tools.permission.profiles import get_profile

        parent = MagicMock()
        parent.permission_manager = PermissionManager(
            global_config=get_profile("dangerous"), active_profile="dangerous"
        )
        child = MagicMock()
        child.permission_manager.active_profile = "normal"
        child.permission_manager.switch_profile.side_effect = RuntimeError("switch failed")
        with pytest.raises(RuntimeError, match="Failed to inherit permission profile 'dangerous'"):
            inherit_parent_permission_profile(
                parent_node=parent,
                agent_config=mock_agent_config,
                node=child,
            )

    @pytest.mark.asyncio
    async def test_task_applies_parent_request_profile_to_created_child(self, mock_agent_config):
        from datus.tools.permission.permission_manager import PermissionManager
        from datus.tools.permission.profiles import get_profile

        mock_agent_config._raw_permissions = {}
        tool = SubAgentTaskTool(agent_config=mock_agent_config)
        parent = MagicMock()
        parent.permission_manager = PermissionManager(
            global_config=get_profile("dangerous"), active_profile="dangerous"
        )
        parent.proxy_tool_patterns = []
        parent.session_id = None
        tool.set_parent_node(parent)
        action = Mock(spec=ActionHistory)
        action.status = ActionStatus.SUCCESS
        action.role = ActionRole.ASSISTANT
        action.output = {"response": "ok", "success": True}
        child = MagicMock()
        child.permission_manager = PermissionManager(global_config=get_profile("normal"), active_profile="normal")

        async def stream(_history):
            yield action

        child.execute_stream_with_interactions = stream
        with patch.object(tool, "_create_node", return_value=child):
            with patch.object(tool, "_build_node_input", return_value=Mock()):
                result = await tool.task(type="gen_sql", prompt="query")
        assert result.success == 1
        assert child.permission_manager.active_profile == "dangerous"


@pytest.mark.ci
class TestEnterpriseAgentAclGate:
    def test_enterprise_available_types_follow_effective_agent_acl(self, mock_agent_config):
        mock_agent_config._enterprise_enabled = True
        mock_agent_config._enterprise_allowed_agent_ids = {"explore", "ask_metrics"}
        mock_agent_config.principal = {"permissions": []}
        tool = SubAgentTaskTool(agent_config=mock_agent_config)
        available = set(tool._get_available_types())
        assert "explore" in available
        assert "ask_metrics" in available
        assert "gen_sql" not in available
        assert "gen_skill" not in available
        assert "scheduler" not in available
        assert "gen_dashboard" not in available

    def test_enterprise_available_types_ignore_module_permissions(self, mock_agent_config):
        mock_agent_config._enterprise_enabled = True
        mock_agent_config._enterprise_allowed_agent_ids = {"gen_sql", "gen_visual_dashboard"}
        mock_agent_config.principal = {"permissions": []}
        tool = SubAgentTaskTool(agent_config=mock_agent_config)
        available = set(tool._get_available_types())
        assert "gen_sql" in available
        assert "gen_visual_dashboard" in available
        assert "gen_dashboard" not in available
        assert "gen_job" not in available

    @pytest.mark.asyncio
    async def test_denies_task_when_agent_acl_does_not_allow_target(self, mock_agent_config):
        mock_agent_config._enterprise_enabled = True
        mock_agent_config._enterprise_allowed_agent_ids = {"chat"}
        mock_agent_config._request_user_id = "user-1"
        tool = SubAgentTaskTool(agent_config=mock_agent_config)
        result = await tool._execute_node("gen_visual_dashboard", "edit dashboards", "edit dashboards")
        assert result.success == 0
        assert "Unknown or disallowed subagent type" in result.error
        assert "module.dashboard.query" not in result.error

    def test_allows_task_target_from_effective_agent_acl(self, mock_agent_config):
        mock_agent_config._enterprise_enabled = True
        mock_agent_config._enterprise_allowed_agent_ids = {"gen_visual_dashboard"}
        assert enterprise_agent_acl_denial(mock_agent_config, "gen_visual_dashboard") is None

    def test_custom_agent_is_filtered_by_acl_not_node_class_module(self):
        config = Mock(spec=AgentConfig)
        config._enterprise_enabled = True
        config._enterprise_allowed_agent_ids = {"sales_dashboard_ask"}
        config.current_datasource = "default"
        config.agentic_nodes = {"sales_dashboard_ask": {"node_class": "ask_dashboard", "artifact_slug": "sales"}}
        tool = SubAgentTaskTool(agent_config=config)
        assert "sales_dashboard_ask" in tool._get_available_types()


def _build_persistent_mock_node(
    *,
    node_name: str = "gen_sql",
    session_id_to_assign: str = "gen_sql_session_abc12345",
    output: dict = None,
    status: ActionStatus = ActionStatus.SUCCESS,
    role: ActionRole = ActionRole.TOOL,
):
    """Construct a MagicMock that behaves like an AgenticNode for task-tool tests.

    The mock yields one action through ``execute_stream_with_interactions`` and
    exposes the AgenticNode surface that ``_execute_node`` touches:
    ``session_id``, ``session_subdir``, ``_session``, ``_session_manager``,
    ``session_manager.session_exists``, ``get_node_name``.
    """
    if output is None:
        output = {"sql": "SELECT 1", "response": "ok", "tokens_used": 10}
    mock_action = Mock(spec=ActionHistory)
    mock_action.status = status
    mock_action.role = role
    mock_action.output = output
    mock_node = MagicMock()
    mock_node.session_id = session_id_to_assign
    mock_node.session_subdir = None
    mock_node._session = None
    mock_node._session_manager = MagicMock()
    mock_node.session_manager = mock_node._session_manager
    mock_node.session_manager.session_exists.return_value = True
    mock_node.get_node_name.return_value = node_name

    async def _mock_stream(ahm):
        yield mock_action

    mock_node.execute_stream_with_interactions = _mock_stream
    mock_node.execute_stream = _mock_stream
    return mock_node


@pytest.mark.ci
class TestSessionPersistenceDownstream:
    @pytest.mark.asyncio
    async def test_persists_delegation_before_child_stream_starts(self, task_tool):
        """The parent sidecar gets the child link before any child action runs."""
        parent = MagicMock()
        parent.session_id = "chat_session_parent01"
        parent.scope = "alice"
        parent.proxy_tool_patterns = None
        parent.session_manager.append_subagent_event_async = AsyncMock()
        task_tool.set_parent_node(parent)
        node = _build_persistent_mock_node(session_id_to_assign="gen_sql_session_child01")
        node.scope = None

        async def _stream(_ahm):
            assert parent.session_manager.append_subagent_event_async.await_count == 1
            assert node.scope == "alice"
            yield Mock(
                spec=ActionHistory,
                status=ActionStatus.SUCCESS,
                role=ActionRole.TOOL,
                output={"sql": "SELECT 1", "response": "ok", "tokens_used": 1},
            )

        node.execute_stream = _stream
        node.execute_stream_with_interactions = _stream
        with patch.object(task_tool, "_create_node", return_value=node):
            with patch.object(task_tool, "_build_node_input", return_value=Mock()):
                result = await task_tool.task(
                    type="gen_sql", prompt="inspect orders", description="inspect schema", call_id="task-call-1"
                )
        assert result.success == 1
        parent.session_manager.append_subagent_event_async.assert_awaited_once()
        session_id, event = parent.session_manager.append_subagent_event_async.await_args.args
        assert session_id == "chat_session_parent01"
        assert event.parent_action_id == "task-call-1"
        assert event.child_session_id == "gen_sql_session_child01"
        assert event.subagent_type == "gen_sql"
        assert event.arguments == {"type": "gen_sql", "prompt": "inspect orders", "description": "inspect schema"}

    @pytest.mark.asyncio
    async def test_delegation_sidecar_failure_does_not_stop_child(self, task_tool):
        """Display-sidecar availability must not become an execution dependency."""
        parent = MagicMock()
        parent.session_id = "chat_session_parent01"
        parent.proxy_tool_patterns = None
        parent.session_manager.append_subagent_event_async = AsyncMock(side_effect=RuntimeError("store down"))
        task_tool.set_parent_node(parent)
        node = _build_persistent_mock_node(session_id_to_assign="gen_sql_session_child01")
        with patch.object(task_tool, "_create_node", return_value=node):
            with patch.object(task_tool, "_build_node_input", return_value=Mock()):
                result = await task_tool.task(
                    type="gen_sql", prompt="inspect orders", description="inspect schema", call_id="task-call-1"
                )
        assert result.success == 1
        parent.session_manager.append_subagent_event_async.assert_awaited_once()

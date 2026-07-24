# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream permission-hook regressions."""

from unittest.mock import MagicMock

import pytest

from datus.cli.execution_state import InteractionBroker
from datus.tools.permission.permission_config import PermissionConfig, PermissionLevel, PermissionRule
from datus.tools.permission.permission_hooks import FilesystemPolicy, PermissionDeniedException, PermissionHooks
from datus.tools.permission.permission_manager import PermissionManager
from datus.tools.registry.tool_registry import ToolRegistry


@pytest.fixture
def mock_broker():
    return MagicMock(spec=InteractionBroker)


def _build_hooks(broker, tmp_path, *, node_name: str, node_class: str):
    registry = ToolRegistry()
    fs_tools = []
    for name in ("read_file", "write_file", "edit_file", "delete_file", "glob", "grep"):
        mock_tool = MagicMock()
        mock_tool.name = name
        fs_tools.append(mock_tool)
    registry.register_tools("filesystem_tools", fs_tools)

    deny_write = PermissionRule(
        tool="filesystem_tools",
        pattern="write_file",
        permission=PermissionLevel.DENY,
    )
    manager = PermissionManager(
        global_config=PermissionConfig(default_permission=PermissionLevel.ASK, rules=[deny_write]),
        active_profile="normal",
    )
    project = tmp_path / "proj"
    project.mkdir()
    hooks = PermissionHooks(
        broker=broker,
        permission_manager=manager,
        node_name=node_name,
        node_class=node_class,
        tool_registry=registry,
        fs_policy=FilesystemPolicy(root_path=project, current_node=node_name),
    )
    return hooks, project


def _ctx_for(path: str):
    ctx = MagicMock()
    ctx.tool_arguments = f'{{"path": "{path}"}}'
    return ctx


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.mark.parametrize("node_name", ["dashboard_agent_42", "dashboard_edit__edit_2"])
@pytest.mark.asyncio
async def test_visual_dashboard_alias_uses_canonical_node_class(mock_broker, tmp_path, node_name: str) -> None:
    """Custom Agent ids and edit-session aliases retain the dashboard carve-out."""
    hooks, project = _build_hooks(
        mock_broker,
        tmp_path,
        node_name=node_name,
        node_class="gen_visual_dashboard",
    )
    target = project / "dashboards/sales_live/render/app.jsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("")

    await hooks.on_tool_start(
        _ctx_for("dashboards/sales_live/render/app.jsx"),
        MagicMock(),
        _tool("write_file"),
    )

    mock_broker.request.assert_not_called()


@pytest.mark.asyncio
async def test_alias_without_visual_artifact_node_class_remains_denied(mock_broker, tmp_path) -> None:
    """An artifact-looking alias must not grant write capability by name alone."""
    hooks, project = _build_hooks(
        mock_broker,
        tmp_path,
        node_name="dashboard_edit__forged",
        node_class="chat",
    )
    target = project / "dashboards/sales_live/render/app.jsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("")

    with pytest.raises(PermissionDeniedException):
        await hooks.on_tool_start(
            _ctx_for("dashboards/sales_live/render/app.jsx"),
            MagicMock(),
            _tool("write_file"),
        )

    mock_broker.request.assert_not_called()

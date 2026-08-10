# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream permission-hook regressions."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from datus.cli.execution_state import InteractionBroker
from datus.tools.permission.permission_config import (
    PermissionConfig,
    PermissionLevel,
    PermissionRule,
    SqlStatementRules,
)
from datus.tools.permission.permission_hooks import FilesystemPolicy, PermissionDeniedException, PermissionHooks
from datus.tools.permission.permission_manager import PermissionManager
from datus.tools.permission.profiles import get_profile
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


def _build_sql_hooks(broker, config, *, project_sql_allows=None, business_datasource_read_only=False):
    registry = ToolRegistry()
    tool = MagicMock()
    tool.name = "execute_sql"
    registry.register_tools("db_tools", [tool])
    manager = PermissionManager(global_config=config, project_sql_allows=project_sql_allows)
    return PermissionHooks(
        broker=broker,
        permission_manager=manager,
        node_name="chat",
        tool_registry=registry,
        business_datasource_read_only=business_datasource_read_only,
    )


def _sql_context(sql: str):
    context = MagicMock()
    context.tool_arguments = json.dumps({"sql": sql})
    return context


def _sql_tool():
    tool = MagicMock()
    tool.name = "execute_sql"
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


@pytest.mark.parametrize("profile", ["normal", "auto", "dangerous"])
@pytest.mark.parametrize(
    ("sql", "operation"),
    [
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET a = 1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE", "MERGE"),
        ("DROP TABLE t", "DROP"),
        ("TRUNCATE TABLE t", "TRUNCATE"),
    ],
)
@pytest.mark.asyncio
async def test_enterprise_read_only_denies_before_any_confirmation(mock_broker, profile, sql, operation):
    hooks = _build_sql_hooks(
        mock_broker,
        get_profile(profile),
        business_datasource_read_only=True,
    )
    mock_broker.request = AsyncMock(return_value=[["y"]])

    with pytest.raises(
        PermissionDeniedException,
        match=rf"ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY: operation='{operation}'",
    ):
        await hooks.on_tool_start(_sql_context(sql), MagicMock(), _sql_tool())

    mock_broker.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_enterprise_read_only_ignores_existing_project_grant(mock_broker):
    hooks = _build_sql_hooks(
        mock_broker,
        PermissionConfig(
            default_permission=PermissionLevel.ASK,
            rules=[],
            sql_statements=SqlStatementRules(write=PermissionLevel.ALLOW),
        ),
        project_sql_allows=["delete"],
        business_datasource_read_only=True,
    )

    with pytest.raises(PermissionDeniedException, match="operation='DELETE'"):
        await hooks.on_tool_start(_sql_context("DELETE FROM t"), MagicMock(), _sql_tool())

    mock_broker.request.assert_not_called()


@pytest.mark.asyncio
async def test_enterprise_read_only_still_allows_select(mock_broker):
    hooks = _build_sql_hooks(
        mock_broker,
        PermissionConfig(
            default_permission=PermissionLevel.ASK,
            rules=[],
            sql_statements=SqlStatementRules(),
        ),
        business_datasource_read_only=True,
    )

    await hooks.on_tool_start(_sql_context("SELECT * FROM t"), MagicMock(), _sql_tool())

    mock_broker.request.assert_not_called()


@pytest.mark.asyncio
async def test_enterprise_read_only_reuses_statement_classification(mock_broker, monkeypatch):
    hooks = _build_sql_hooks(
        mock_broker,
        get_profile("normal"),
        business_datasource_read_only=True,
    )
    from datus.tools import business_datasource_policy

    original_parse = business_datasource_policy.parse_sql_statement_kind
    parse_calls = []

    def count_parse(sql, dialect=""):
        parse_calls.append((sql, dialect))
        return original_parse(sql, dialect)

    monkeypatch.setattr(business_datasource_policy, "parse_sql_statement_kind", count_parse)

    await hooks.on_tool_start(_sql_context("SELECT * FROM t"), MagicMock(), _sql_tool())

    assert parse_calls == [("SELECT * FROM t", "")]

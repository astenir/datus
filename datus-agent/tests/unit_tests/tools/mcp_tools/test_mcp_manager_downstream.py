"""Downstream MCP manager coverage kept out of the upstream test file."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from datus.tools.mcp_tools.mcp_config import STDIOServerConfig, ToolFilterConfig
from datus.tools.mcp_tools.mcp_manager import MCPManager


def _make_manager(tmp_path: Path) -> MCPManager:
    mock_path_manager = MagicMock()
    config_file = tmp_path / "conf" / ".mcp.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    mock_path_manager.mcp_config_path.return_value = config_file
    mock_path_manager.ensure_dirs.return_value = None

    with patch("datus.utils.path_manager.get_path_manager", return_value=mock_path_manager):
        return MCPManager()


def test_update_server_success(tmp_path):
    manager = _make_manager(tmp_path)
    manager.add_server(STDIOServerConfig(name="srv", command="python"))

    success, msg = manager.update_server("srv", STDIOServerConfig(name="srv", command="node", cwd="/workspace"))

    assert success is True
    assert "updated server" in msg
    assert manager.config.servers["srv"].command == "node"
    assert manager.config.servers["srv"].cwd == "/workspace"


def test_update_server_preserves_tool_filter(tmp_path):
    manager = _make_manager(tmp_path)
    tool_filter = ToolFilterConfig(allowed_tool_names=["read"])
    manager.add_server(STDIOServerConfig(name="srv", command="python", tool_filter=tool_filter))

    success, msg = manager.update_server("srv", STDIOServerConfig(name="srv", command="node"))

    assert success is True
    assert "updated server" in msg
    assert manager.config.servers["srv"].tool_filter == tool_filter


def test_update_server_not_found(tmp_path):
    manager = _make_manager(tmp_path)

    success, msg = manager.update_server("missing", STDIOServerConfig(name="missing", command="python"))

    assert success is False
    assert "not found" in msg


def test_runtime_server_receives_persisted_tool_filter(tmp_path):
    manager = _make_manager(tmp_path)
    config = STDIOServerConfig(
        name="srv",
        command="python",
        tool_filter=ToolFilterConfig(allowed_tool_names=["read"], blocked_tool_names=["delete"]),
    )

    server, _ = manager._create_server_instance(config)

    assert server.tool_filter == {
        "allowed_tool_names": ["read"],
        "blocked_tool_names": ["delete"],
    }

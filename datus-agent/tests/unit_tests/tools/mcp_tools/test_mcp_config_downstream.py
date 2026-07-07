"""Downstream MCP config coverage kept out of the upstream test file."""

from datus.tools.mcp_tools.mcp_config import MCPConfig, MCPServerConfig, STDIOServerConfig


def test_stdio_connection_info_includes_cwd():
    cfg = STDIOServerConfig(name="s", command="node", args=["server.js"], env={"FOO": "bar"}, cwd="/workspace")

    info = cfg.get_connection_info()

    assert info["cwd"] == "/workspace"


def test_stdio_from_config_format_parses_cwd():
    cfg = MCPServerConfig.from_config_format(
        "srv",
        {"type": "stdio", "command": "python", "args": ["-m", "app"], "cwd": "/workspace"},
    )

    assert isinstance(cfg, STDIOServerConfig)
    assert cfg.cwd == "/workspace"


def test_mcp_config_to_config_format_preserves_stdio_cwd():
    cfg = MCPConfig()
    cfg.add_server(STDIOServerConfig(name="s", command="python", args=["-m", "app"], cwd="/workspace"))

    out = cfg.to_config_format()

    assert out["mcpServers"]["s"]["cwd"] == "/workspace"

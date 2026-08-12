from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import Tool as MCPTool

from datus.models.mcp_connection_options_downstream import connection_failure_options
from datus.models.mcp_utils import PrefixedMCPServer, multiple_mcp_servers


class _FakeServer:
    """Minimal in-memory MCP server double for lifecycle/tool assertions."""

    def __init__(self, name: str, tools: list[MCPTool]):
        self.name = name
        self._tools = tools
        self.called_with: list[str] = []
        self.use_structured_content = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def list_tools(self, run_context=None, agent=None):
        return list(self._tools)

    async def call_tool(self, tool_name, arguments=None):
        self.called_with.append(tool_name)
        return "ok"


def _fake_tool(name: str) -> MCPTool:
    return MCPTool(name=name, inputSchema={"type": "object", "properties": {}})


@pytest.mark.asyncio
async def test_connection_failure_is_reported_once_and_other_execution_can_continue():
    server = MagicMock()
    server.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
    server.__aexit__ = AsyncMock(return_value=False)
    failures: list[tuple[str, str]] = []

    with patch("datus.models.mcp_utils.asyncio.sleep", new=AsyncMock()):
        async with multiple_mcp_servers(
            {"remote": server},
            on_connection_failure=lambda name, error: failures.append((name, error)),
            max_retries=1,
        ) as connected:
            assert connected == {}

    assert failures == [
        (
            "remote",
            "Failed to connect to MCP server. Please check the server address and network connectivity.",
        )
    ]
    assert server.__aenter__.await_count == 1


def test_chat_mcp_failure_callback_limits_connection_attempts_without_changing_the_default():
    callback = MagicMock()

    assert connection_failure_options({"mcp_connection_failure_callback": callback}) == {
        "on_connection_failure": callback,
        "max_retries": 1,
    }
    assert connection_failure_options({}) == {}


@pytest.mark.asyncio
async def test_mcp_connection_default_retries_remain_three_attempts():
    server = MagicMock()
    server.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))

    with patch("datus.models.mcp_utils.asyncio.sleep", new_callable=AsyncMock):
        async with multiple_mcp_servers({"remote": server}) as connected:
            assert connected == {}

    assert server.__aenter__.await_count == 3


@pytest.mark.asyncio
async def test_single_mcp_server_keeps_original_tool_names():
    """With one configured server the wrapper is a no-op and tool names stay raw."""

    server = _FakeServer("only", [_fake_tool("NM007399")])

    async with multiple_mcp_servers({"only": server}) as connected:
        assert connected["only"] is server
        tools = await connected["only"].list_tools()
        assert [tool.name for tool in tools] == ["NM007399"]


@pytest.mark.asyncio
async def test_duplicate_tool_names_across_servers_are_prefix_isolated():
    """Two servers exposing the same tool names coexist via server-qualified names.

    The Agents SDK rejects duplicate tool names across MCP servers; wrapping
    each connected server with ``PrefixedMCPServer`` gives every tool a
    globally unique ``<server_name>_<tool_name>`` name, and ``call_tool``
    routes back to the underlying server with the original name.
    """

    enterprise = _FakeServer("enterprise_search", [_fake_tool("NM007399"), _fake_tool("search_doc")])
    personal = _FakeServer("personal_" + "a" * 32, [_fake_tool("NM007399")])

    async with multiple_mcp_servers(
        {"enterprise_search": enterprise, "personal_" + "a" * 32: personal}
    ) as connected:
        assert connected["enterprise_search"] is not enterprise
        enterprise_tools = await connected["enterprise_search"].list_tools()
        personal_tools = await connected["personal_" + "a" * 32].list_tools()
        names = {tool.name for tool in enterprise_tools} | {tool.name for tool in personal_tools}

        assert "NM007399" not in names
        assert "enterprise_search_NM007399" in names
        assert "enterprise_search_search_doc" in names
        assert f"personal_{'a' * 32}_NM007399" in names
        assert len(names) == 3

        await connected["enterprise_search"].call_tool("enterprise_search_NM007399", {})
        await connected["personal_" + "a" * 32].call_tool(f"personal_{'a' * 32}_NM007399", {})
        assert enterprise.called_with == ["NM007399"]
        assert personal.called_with == ["NM007399"]


@pytest.mark.asyncio
async def test_prefixing_follows_configured_server_count_when_one_connection_fails():
    """Prefixing keys off the configured set, not the connection outcome.

    The prompt-side tool-name advertisement uses the same configured-count
    rule, so the SDK tool schema and the advertised names must stay aligned
    even when a server fails to connect.
    """

    ok = _FakeServer("ok_server", [_fake_tool("NM007399")])
    failing = MagicMock()
    failing.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
    failing.__aexit__ = AsyncMock(return_value=False)

    with patch("datus.models.mcp_utils.asyncio.sleep", new=AsyncMock()):
        async with multiple_mcp_servers(
            {"ok_server": ok, "bad_server": failing},
            max_retries=1,
        ) as connected:
            assert list(connected) == ["ok_server"]
            tools = await connected["ok_server"].list_tools()
            assert [tool.name for tool in tools] == ["ok_server_NM007399"]


@pytest.mark.asyncio
async def test_prefixed_mcp_server_delegates_lifecycle_and_structured_content():
    server = _FakeServer("erp", [_fake_tool("NM007399")])
    server.use_structured_content = True
    wrapped = PrefixedMCPServer(server, prefix="erp_")

    assert wrapped.name == "erp"
    assert wrapped.use_structured_content is True
    assert wrapped._delegate_server is server
    tools = await wrapped.list_tools()
    assert [tool.name for tool in tools] == ["erp_NM007399"]
    # Unprefixed names pass through untouched (defensive routing).
    await wrapped.call_tool("NM007399", {})
    assert server.called_with == ["NM007399"]

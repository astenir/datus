from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.models.mcp_connection_options_downstream import connection_failure_options
from datus.models.mcp_utils import multiple_mcp_servers


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

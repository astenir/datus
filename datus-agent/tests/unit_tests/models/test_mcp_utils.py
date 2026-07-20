from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        ) as connected:
            assert connected == {}

    assert failures == [("remote", "connection refused")]

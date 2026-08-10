"""Enterprise MCP credential isolation and secret handling coverage."""

import json

import pytest

from datus.tools.mcp_tools.mcp_config import HTTPServerConfig, MCPAuthConfig
from datus.tools.mcp_tools.mcp_credentials import MCPRequestCredentials
from datus.tools.mcp_tools.mcp_manager import _safe_operation_error
from tests.unit_tests.tools.mcp_tools.test_mcp_manager import _make_manager


class TestMCPManagerCredentialSecurity:
    def test_redacts_bearer_and_url_from_http_error(self):
        error = RuntimeError("HTTP 403 for https://private.example/mcp Authorization: Bearer should-not-appear")

        message = _safe_operation_error(error)

        assert message == "MCP server returned HTTP 403."
        assert "should-not-appear" not in message
        assert "private.example" not in message

    def test_static_token_round_trip_and_file_permissions(self, tmp_path):
        manager = _make_manager(tmp_path)
        manager.config.add_server(
            HTTPServerConfig(
                name="secured",
                url="http://example.com/mcp",
                auth=MCPAuthConfig(mode="static_bearer", token="stored-value"),
            )
        )

        assert manager.save_config() is True
        persisted = json.loads(manager.config_path.read_text())
        assert persisted["mcpServers"]["secured"]["auth"] == {
            "mode": "static_bearer",
            "token": "stored-value",
        }
        assert manager.config_path.stat().st_mode & 0o777 == 0o600

        loaded = _make_manager(tmp_path).get_server_config("secured")
        assert loaded.auth.token == "stored-value"
        assert "stored-value" not in str(loaded.model_dump())

    def test_request_bearer_headers_are_isolated_per_connection(self, tmp_path):
        manager = _make_manager(tmp_path)
        config = HTTPServerConfig(
            name="secured",
            url="http://example.com/mcp",
            headers={"X-Tenant": "acme"},
            auth=MCPAuthConfig(mode="request_bearer"),
        )

        alice = manager._resolve_remote_headers(
            config.headers,
            config=config,
            request_credentials=MCPRequestCredentials(bearer_token="alice-value", user_id="alice"),
        )
        bob = manager._resolve_remote_headers(
            config.headers,
            config=config,
            request_credentials=MCPRequestCredentials(bearer_token="bob-value", user_id="bob"),
        )

        assert alice == {"X-Tenant": "acme", "Authorization": "Bearer alice-value"}
        assert bob == {"X-Tenant": "acme", "Authorization": "Bearer bob-value"}
        assert config.headers == {"X-Tenant": "acme"}
        assert config.auth.token is None

    def test_request_bearer_fails_closed_without_request_credentials(self, tmp_path):
        manager = _make_manager(tmp_path)
        config = HTTPServerConfig(
            name="secured",
            url="http://example.com/mcp",
            auth=MCPAuthConfig(mode="request_bearer"),
        )

        with pytest.raises(ValueError, match="MCP_AUTH_CONTEXT_UNAVAILABLE"):
            manager._resolve_remote_headers({}, config=config, request_credentials=None)

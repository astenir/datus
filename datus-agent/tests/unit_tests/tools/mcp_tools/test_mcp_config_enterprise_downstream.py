"""Enterprise MCP authentication model coverage kept out of upstream tests."""

import pytest
from pydantic import ValidationError

from datus.tools.mcp_tools.mcp_config import MCPAuthConfig, MCPAuthMode


class TestMCPAuthConfig:
    def test_normalizes_static_bearer_token(self):
        auth = MCPAuthConfig(mode="static_bearer", token="  Bearer fixed-value  ")

        assert auth.mode == MCPAuthMode.STATIC_BEARER
        assert auth.token == "fixed-value"
        assert auth.credential_configured is True

    def test_request_bearer_has_credential_source_without_token(self):
        auth = MCPAuthConfig(mode="request_bearer")

        assert auth.credential_configured is True
        assert auth.token is None

    def test_static_bearer_requires_token(self):
        with pytest.raises(ValidationError):
            MCPAuthConfig(mode="static_bearer")

    def test_non_static_mode_rejects_token(self):
        with pytest.raises(ValidationError):
            MCPAuthConfig(mode="request_bearer", token="must-not-persist")

    def test_model_dump_excludes_static_token(self):
        auth = MCPAuthConfig(mode="static_bearer", token="dump-secret")

        assert "dump-secret" not in str(auth.model_dump())

# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for datus_semantic_core.config"""

from datus_semantic_core.config import SemanticAdapterConfig


class TestSemanticAdapterConfig:
    def test_defaults(self):
        c = SemanticAdapterConfig()
        assert c.datasource is None
        assert c.timeout_seconds == 30
        assert c.api_base_url is None
        assert c.auth_token is None
        assert c.username is None
        assert c.password is None

    def test_existing_fields(self):
        c = SemanticAdapterConfig(datasource="prod", timeout_seconds=60)
        assert c.datasource == "prod"
        assert c.timeout_seconds == 60

    def test_auth_fields(self):
        expected_auth = "test-auth-value"
        expected_pass = "test-pass-value"
        c = SemanticAdapterConfig(
            api_base_url="http://localhost:4000/cubejs-api",
            auth_token=expected_auth,
            username="admin",
            password=expected_pass,
        )
        assert c.api_base_url == "http://localhost:4000/cubejs-api"
        assert c.auth_token == expected_auth
        assert c.username == "admin"
        assert c.password == expected_pass

    def test_extra_fields_allowed(self):
        c = SemanticAdapterConfig(custom_field="custom")
        assert c.custom_field == "custom"

    def test_backward_compat(self):
        c = SemanticAdapterConfig(datasource="test")
        assert c.api_base_url is None
        assert c.auth_token is None

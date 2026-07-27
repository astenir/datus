"""Tests for datus.api.service — FastAPI app creation and DatusAPIService."""

import argparse
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseDatasourceGrantStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.service import create_app


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class TestCreateAppDownstream:
    """Tests for create_app — FastAPI application factory."""

    def test_enterprise_mode_disables_legacy_auth_and_workflow_routes(self, monkeypatch):
        """Enterprise mode must not expose legacy client-token workflow APIs."""
        args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
        app = create_app(args)
        audit_sink = CollectingAuditSink()
        with TestClient(app, raise_server_exceptions=False) as client:
            monkeypatch.setattr(
                deps,
                "_enterprise_extensions",
                EnterpriseExtensions(
                    enabled=True,
                    authorization_provider=LocalAuthorizationProvider(),
                    config_projector=PassthroughConfigProjector(),
                    session_owner_store=InMemorySessionOwnerStore(),
                    audit_sink=audit_sink,
                    datasource_grant_store=InMemoryEnterpriseDatasourceGrantStore(),
                ),
            )
            token_response = client.post(
                "/auth/token",
                data={
                    "client_id": "datus_client",
                    "client_secret": "datus_secret_key",
                    "grant_type": "client_credentials",
                },
            )
            workflow_response = client.post(
                "/workflows/run",
                json={"workflow": "nl2sql", "datasource": "default", "task": "List rows", "mode": "sync"},
            )
            feedback_response = client.post("/workflows/feedback", json={"task_id": "task-1", "status": "success"})
        assert token_response.status_code == 404
        assert workflow_response.status_code == 404
        assert feedback_response.status_code == 404
        assert token_response.json()["detail"]["errorCode"] == "ENTERPRISE_LEGACY_API_DISABLED"
        assert workflow_response.json()["detail"]["errorCode"] == "ENTERPRISE_LEGACY_API_DISABLED"
        assert feedback_response.json()["detail"]["errorCode"] == "ENTERPRISE_LEGACY_API_DISABLED"
        assert [event.action for event in audit_sink.events] == [
            "system.route_disabled",
            "system.route_disabled",
            "system.route_disabled",
        ]
        assert [event.metadata for event in audit_sink.events] == [
            {"operation": "auth.token_legacy"},
            {"operation": "workflow.legacy"},
            {"operation": "workflow.legacy"},
        ]

    def test_lifespan_closes_enterprise_extensions(self, monkeypatch):
        """Application shutdown closes loaded enterprise extension providers."""

        class _FakeDatusAPIService:
            def __init__(self, args):
                self.args = args
                self.agent_config = SimpleNamespace(api_config={}, enterprise_config={})

            async def initialize(self):
                return None

        close = AsyncMock()
        extensions = SimpleNamespace(enabled=False, close=close)
        service_module = importlib.import_module("datus.api.service")
        monkeypatch.setattr(service_module, "DatusAPIService", _FakeDatusAPIService)
        monkeypatch.setattr(service_module, "load_enterprise_extensions", lambda _config: extensions)
        args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
        app = create_app(args)
        try:
            with TestClient(app):
                pass
        finally:
            deps._enterprise_extensions = None
        close.assert_awaited_once()

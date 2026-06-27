import argparse
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import AuditEvent as CoreAuditEvent
from datus.api.service import create_app
from datus_enterprise.api import admin_audit_routes


def _svc():
    return SimpleNamespace(agent_config=SimpleNamespace())


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class QueryableAuditSink(CollectingAuditSink):
    def __init__(self, events=None):
        super().__init__()
        self.source_events = list(events or [])
        self.queries = []

    async def query_events(
        self,
        *,
        limit: int,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        decision: str | None = None,
    ):
        self.queries.append(
            {
                "limit": limit,
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "decision": decision,
            }
        )
        return self.source_events


def _install_extensions(monkeypatch, audit_sink):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_audit_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    return TestClient(app)


def test_admin_audit_logs_rejects_without_admin_audit(monkeypatch):
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})
    _install_extensions(monkeypatch, NoopAuditSink())

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs")

    assert response.status_code == 403
    assert "module.admin.audit" in response.json()["detail"]


def test_admin_audit_logs_returns_unavailable_when_sink_is_write_only(monkeypatch):
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="u1", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "AUDIT_QUERY_UNAVAILABLE"
    assert body["errorMessage"] == "The configured audit sink does not support audit log queries."

    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "module.admin.audit"
    assert event.resource_type == "audit_log"
    assert event.resource_id is None
    assert event.decision == "deny"
    assert event.reason == "audit query unavailable"
    assert event.metadata == {"operation": "list_audit_logs"}


def test_admin_audit_logs_forwards_filters_returns_entries_and_audits(monkeypatch):
    audit_event = CoreAuditEvent(
        user_id="u2",
        action="chat.stream",
        resource_type="session",
        resource_id="s1",
        decision="allow",
        reason=None,
        request_id="r1",
        metadata={"operation": "stream", "sql": "redacted"},
    )
    audit_sink = QueryableAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={
                "limit": 25,
                "user_id": "u2",
                "action": "chat.stream",
                "resource_type": "session",
                "resource_id": "s1",
                "decision": "allow",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == [
        {
            "user_id": "u2",
            "action": "chat.stream",
            "resource_type": "session",
            "resource_id": "s1",
            "decision": "allow",
            "reason": None,
            "request_id": "r1",
            "metadata": {"operation": "stream", "sql": "redacted"},
        }
    ]
    assert audit_sink.queries == [
        {
            "limit": 25,
            "user_id": "u2",
            "action": "chat.stream",
            "resource_type": "session",
            "resource_id": "s1",
            "decision": "allow",
        }
    ]

    event = audit_sink.events[-1]
    assert event.user_id == "admin"
    assert event.action == "module.admin.audit"
    assert event.resource_type == "audit_log"
    assert event.resource_id is None
    assert event.decision == "allow"
    assert event.metadata == {"operation": "list_audit_logs", "count": 1}


def test_enterprise_admin_audit_routes_are_registered():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/admin/audit-logs" in route_paths

import argparse
import asyncio
import csv
from io import StringIO
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseQuotaStore,
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
        request_id: str | None = None,
        before_id: int | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ):
        self.queries.append(
            {
                "limit": limit,
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "decision": decision,
                "request_id": request_id,
                "before_id": before_id,
                "created_after": created_after,
                "created_before": created_before,
            }
        )
        events = [
            event
            for event in self.source_events
            if (user_id is None or event.user_id == user_id)
            and (action is None or event.action == action)
            and (resource_type is None or event.resource_type == resource_type)
            and (resource_id is None or event.resource_id == resource_id)
            and (decision is None or event.decision == decision)
            and (request_id is None or event.request_id == request_id)
            and (before_id is None or (event.id is not None and event.id < before_id))
            and (created_after is None or (event.created_at is not None and event.created_at >= created_after))
            and (created_before is None or (event.created_at is not None and event.created_at < created_before))
        ]
        return events[:limit]


class QueryableFailingWriteAuditSink(QueryableAuditSink):
    async def write(self, event):
        raise RuntimeError("audit write down")


def _install_extensions(monkeypatch, audit_sink, *, enabled=False, quota_store=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=enabled,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            quota_store=quota_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_audit_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
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
        id=42,
        created_at="2026-07-01T08:00:00Z",
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
    assert body["data"] == {
        "entries": [
            {
                "id": 42,
                "created_at": "2026-07-01T08:00:00Z",
                "user_id": "u2",
                "action": "chat.stream",
                "resource_type": "session",
                "resource_id": "s1",
                "decision": "allow",
                "reason": None,
                "request_id": "r1",
                "metadata": {"operation": "stream", "sql": "redacted"},
            }
        ],
        "limit": 25,
        "before_id": None,
        "next_before_id": None,
        "has_more": False,
    }
    assert audit_sink.queries == [
        {
            "limit": 26,
            "user_id": "u2",
            "action": "chat.stream",
            "resource_type": "session",
            "resource_id": "s1",
            "decision": "allow",
            "request_id": None,
            "before_id": None,
            "created_after": None,
            "created_before": None,
        }
    ]

    event = audit_sink.events[-1]
    assert event.user_id == "admin"
    assert event.action == "module.admin.audit"
    assert event.resource_type == "audit_log"
    assert event.resource_id is None
    assert event.decision == "allow"
    assert event.metadata == {"operation": "list_audit_logs", "count": 1, "has_more": False}


def test_admin_audit_logs_returns_cursor_page(monkeypatch):
    audit_sink = QueryableAuditSink(
        [
            CoreAuditEvent(
                id=5,
                created_at="2026-07-01T09:05:00Z",
                user_id="u2",
                action="chat.stream",
                resource_type="session",
                resource_id="s5",
                decision="allow",
            ),
            CoreAuditEvent(
                id=4,
                created_at="2026-07-01T09:04:00Z",
                user_id="u2",
                action="chat.stream",
                resource_type="session",
                resource_id="s4",
                decision="allow",
            ),
            CoreAuditEvent(
                id=3,
                created_at="2026-07-01T09:03:00Z",
                user_id="u2",
                action="chat.stream",
                resource_type="session",
                resource_id="s3",
                decision="allow",
            ),
            CoreAuditEvent(
                id=2,
                created_at="2026-07-01T09:02:00Z",
                user_id="u2",
                action="chat.stream",
                resource_type="session",
                resource_id="s2",
                decision="allow",
            ),
        ]
    )
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs", params={"limit": 2, "before_id": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [entry["id"] for entry in body["data"]["entries"]] == [4, 3]
    assert body["data"]["limit"] == 2
    assert body["data"]["before_id"] == 5
    assert body["data"]["next_before_id"] == 3
    assert body["data"]["has_more"] is True
    assert audit_sink.queries == [
        {
            "limit": 3,
            "user_id": None,
            "action": None,
            "resource_type": None,
            "resource_id": None,
            "decision": None,
            "request_id": None,
            "before_id": 5,
            "created_after": None,
            "created_before": None,
        }
    ]


def test_admin_audit_logs_filters_request_id_and_time_range(monkeypatch):
    audit_sink = QueryableAuditSink(
        [
            CoreAuditEvent(
                id=10,
                created_at="2026-07-01T09:30:00+00:00",
                user_id="u2",
                action="sql.execute",
                resource_type="datasource",
                resource_id="finance",
                decision="deny",
                request_id="req-1",
            ),
            CoreAuditEvent(
                id=9,
                created_at="2026-07-01T08:30:00+00:00",
                user_id="u2",
                action="sql.execute",
                resource_type="datasource",
                resource_id="finance",
                decision="deny",
                request_id="req-1",
            ),
            CoreAuditEvent(
                id=8,
                created_at="2026-07-01T09:45:00+00:00",
                user_id="u3",
                action="sql.execute",
                resource_type="datasource",
                resource_id="sales",
                decision="deny",
                request_id="req-2",
            ),
        ]
    )
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get(
            "/api/v1/admin/audit-logs",
            params={
                "request_id": "req-1",
                "created_after": "2026-07-01T09:00:00+00:00",
                "created_before": "2026-07-01T10:00:00+00:00",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [entry["id"] for entry in body["data"]["entries"]] == [10]
    assert audit_sink.queries == [
        {
            "limit": 101,
            "user_id": None,
            "action": None,
            "resource_type": None,
            "resource_id": None,
            "decision": None,
            "request_id": "req-1",
            "before_id": None,
            "created_after": "2026-07-01T09:00:00+00:00",
            "created_before": "2026-07-01T10:00:00+00:00",
        }
    ]
    event = audit_sink.events[-1]
    assert event.metadata["request_id"] == "req-1"
    assert event.metadata["created_after"] == "2026-07-01T09:00:00+00:00"
    assert event.metadata["created_before"] == "2026-07-01T10:00:00+00:00"


def test_admin_audit_logs_returns_entries_when_post_query_audit_fails(monkeypatch):
    audit_event = CoreAuditEvent(
        user_id="u2",
        action="chat.stream",
        resource_type="session",
        resource_id="s1",
        decision="allow",
        reason=None,
        request_id="r1",
        metadata={},
    )
    audit_sink = QueryableFailingWriteAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["entries"][0]["resource_id"] == "s1"


def test_admin_audit_log_export_returns_csv_and_audits(monkeypatch):
    audit_event = CoreAuditEvent(
        id=7,
        created_at="2026-07-01T09:00:00Z",
        user_id="u2",
        action="sql.execute",
        resource_type="datasource",
        resource_id="finance",
        decision="deny",
        reason="POLICY_DENIED",
        request_id="r2",
        metadata={"error_code": "POLICY_DENIED", "row_count": 0},
    )
    audit_sink = QueryableAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get(
            "/api/v1/admin/audit-logs/export",
            params={"limit": 10, "resource_type": "datasource", "decision": "deny"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="audit-logs.csv"'
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
            "id": "7",
            "created_at": "2026-07-01T09:00:00Z",
            "user_id": "u2",
            "action": "sql.execute",
            "resource_type": "datasource",
            "resource_id": "finance",
            "decision": "deny",
            "reason": "POLICY_DENIED",
            "request_id": "r2",
            "metadata": '{"error_code": "POLICY_DENIED", "row_count": 0}',
        }
    ]
    assert audit_sink.queries == [
        {
            "limit": 11,
            "user_id": None,
            "action": None,
            "resource_type": "datasource",
            "resource_id": None,
            "decision": "deny",
            "request_id": None,
            "before_id": None,
            "created_after": None,
            "created_before": None,
        }
    ]

    event = audit_sink.events[-1]
    assert event.user_id == "admin"
    assert event.action == "module.admin.audit.export"
    assert event.resource_type == "audit_log"
    assert event.resource_id is None
    assert event.decision == "allow"
    assert event.metadata == {"operation": "export_audit_logs", "count": 1}


def test_admin_audit_log_export_returns_csv_when_post_query_audit_fails(monkeypatch):
    audit_event = CoreAuditEvent(
        user_id="u2",
        action="sql.execute",
        resource_type="datasource",
        resource_id="finance",
        decision="allow",
        reason=None,
        request_id="r2",
        metadata={},
    )
    audit_sink = QueryableFailingWriteAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows[0]["resource_id"] == "finance"


def test_admin_audit_log_export_returns_unavailable_without_quota_store(monkeypatch):
    audit_sink = QueryableAuditSink()
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink, enabled=True, quota_store=None)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_STORE_UNAVAILABLE"
    assert audit_sink.queries == []
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.resource_type == "audit_log"
    assert event.decision == "deny"
    assert event.reason == "quota store unavailable"
    assert event.metadata["quota_resource"] == "admin.audit.export"


def test_admin_audit_log_export_rejects_quota_exceeded(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="admin",
            resource="admin.audit.export",
            limit=1,
            window_seconds=3600,
        )
    )
    asyncio.run(
        quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": "admin"}],
            resource="admin.audit.export",
        )
    )
    audit_sink = QueryableAuditSink()
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink, enabled=True, quota_store=quota_store)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_EXCEEDED"
    assert audit_sink.queries == []
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.resource_type == "audit_log"
    assert event.decision == "deny"
    assert event.reason == "quota exceeded"
    assert event.metadata["resource"] == "admin.audit.export"
    assert event.metadata["used"] == 1


def test_admin_audit_log_export_consumes_quota(monkeypatch):
    audit_event = CoreAuditEvent(
        user_id="u2",
        action="chat.stream",
        resource_type="session",
        resource_id="s1",
        decision="allow",
        reason=None,
        request_id="r1",
        metadata={"operation": "stream"},
    )
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="admin",
            resource="admin.audit.export",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = QueryableAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink, enabled=True, quota_store=quota_store)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="admin", resource="admin.audit.export"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert usage[0]["used"] == 1
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.decision == "allow"
    assert event.metadata["quota_resource"] == "admin.audit.export"
    assert audit_sink.events[-1].action == "module.admin.audit.export"


def test_admin_audit_log_export_returns_unavailable_when_sink_is_write_only(monkeypatch):
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="u1", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "AUDIT_QUERY_UNAVAILABLE"
    event = audit_sink.events[-1]
    assert event.action == "module.admin.audit.export"
    assert event.resource_type == "audit_log"
    assert event.decision == "deny"
    assert event.reason == "audit query unavailable"
    assert event.metadata == {"operation": "export_audit_logs"}


def test_admin_audit_log_export_write_only_sink_does_not_consume_quota(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="admin",
            resource="admin.audit.export",
            limit=1,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink, enabled=True, quota_store=quota_store)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="admin", resource="admin.audit.export"))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "AUDIT_QUERY_UNAVAILABLE"
    assert usage == []
    assert [event.action for event in audit_sink.events] == ["module.admin.audit.export"]


def test_admin_audit_log_export_rejects_without_export_permission(monkeypatch):
    audit_sink = QueryableAuditSink()
    ctx = AppContext(user_id="u1", permissions={"module.admin.audit"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 403
    assert "module.admin.audit.export" in response.json()["detail"]
    assert audit_sink.queries == []


def test_admin_audit_log_export_sanitizes_formula_prefix_cells(monkeypatch):
    audit_event = CoreAuditEvent(
        user_id="\t=cmd",
        action="+SUM(1,1)",
        resource_type="datasource",
        resource_id="@finance",
        decision="deny",
        reason="-POLICY_DENIED",
        request_id=None,
        metadata={"note": "=metadata"},
    )
    audit_sink = QueryableAuditSink([audit_event])
    ctx = AppContext(user_id="admin", permissions={"module.admin.audit.export"})
    _install_extensions(monkeypatch, audit_sink)

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/audit-logs/export")

    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
            "id": "",
            "created_at": "",
            "user_id": "'\t=cmd",
            "action": "'+SUM(1,1)",
            "resource_type": "datasource",
            "resource_id": "'@finance",
            "decision": "deny",
            "reason": "'-POLICY_DENIED",
            "request_id": "",
            "metadata": '{"note": "=metadata"}',
        }
    ]


def test_enterprise_admin_audit_routes_are_registered():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/admin/audit-logs" in route_paths
    assert "/api/v1/admin/audit-logs/export" in route_paths

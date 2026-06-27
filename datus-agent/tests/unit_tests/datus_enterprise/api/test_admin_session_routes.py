import asyncio
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ChatSessionData
from datus.api.services.chat_task_manager import ChatTask, ChatTaskManager
from datus_enterprise.api import admin_session_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class DummyAsyncioTask:
    def __init__(self):
        self.cancelled = False

    def done(self):
        return False

    def cancel(self):
        self.cancelled = True


class FakeChatService:
    def __init__(self, existing=None):
        self.existing = dict(existing or {})
        self.delete_calls = []

    def session_exists(self, session_id, user_id=None):
        return bool(self.existing.get((user_id, session_id), False))

    def delete_session(self, session_id, user_id=None):
        self.delete_calls.append((session_id, user_id))
        self.existing.pop((user_id, session_id), None)
        return Result(success=True, data=ChatSessionData())


class LegacyOwnerStore:
    def __init__(self):
        self.owners = {}

    async def set_owner(self, project_id, session_id, user_id):
        self.owners[(project_id, session_id)] = user_id

    async def get_owner(self, project_id, session_id):
        return self.owners.get((project_id, session_id))

    async def delete_owner(self, project_id, session_id):
        self.owners.pop((project_id, session_id), None)

    async def list_session_ids(self, project_id, user_id):
        return [
            session_id
            for (stored_project, session_id), owner in self.owners.items()
            if stored_project == project_id and owner == user_id
        ]


def _install_extensions(monkeypatch, owner_store, audit_sink):
    monkeypatch.setattr(
        admin_session_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=owner_store,
            audit_sink=audit_sink,
        ),
    )


def _client(ctx, svc):
    app = FastAPI()
    app.include_router(admin_session_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    return TestClient(app)


def _svc(existing=None):
    manager = ChatTaskManager(project_id="project")
    return SimpleNamespace(
        project_id="project",
        task_manager=manager,
        chat=FakeChatService(existing),
    )


def _add_running_task(manager, session_id, owner_user_id):
    asyncio_task = DummyAsyncioTask()
    task = ChatTask(session_id=session_id, asyncio_task=asyncio_task, owner_user_id=owner_user_id)
    manager._tasks[session_id] = task
    return task, asyncio_task


def test_admin_sessions_rejects_without_permission(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.datasources"})

    with _client(ctx, _svc()) as client:
        response = client.get("/api/v1/admin/sessions")

    assert response.status_code == 403
    assert "module.admin.sessions" in response.json()["detail"]


def test_admin_sessions_returns_unavailable_for_global_list_without_store_support(monkeypatch):
    owner_store = LegacyOwnerStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, _svc()) as client:
        response = client.get("/api/v1/admin/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SESSION_LIST_UNAVAILABLE"
    assert body["errorMessage"] == "The configured session owner store does not support admin session listing."
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].metadata == {"operation": "list_admin_sessions"}


def test_admin_sessions_list_merges_owner_records_and_running_tasks(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    asyncio.run(owner_store.set_owner("project", "s2", "bob"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True, ("bob", "s2"): True})
    _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/admin/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    sessions = {item["session_id"]: item for item in body["data"]}
    assert sessions["s1"] == {
        "session_id": "s1",
        "owner_user_id": "alice",
        "status": "persisted",
        "is_running": False,
        "created_at": None,
        "updated_at": None,
        "event_count": 0,
        "exists_on_disk": True,
    }
    assert sessions["s2"]["owner_user_id"] == "bob"
    assert sessions["s2"]["status"] == "running"
    assert sessions["s2"]["is_running"] is True
    assert sessions["s2"]["exists_on_disk"] is True
    assert audit_sink.events[-1].decision == "allow"
    assert audit_sink.events[-1].metadata == {"operation": "list_admin_sessions", "count": 2, "user_id": None}


def test_admin_sessions_user_filter_does_not_include_other_user_runtime_only_tasks(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True, ("bob", "s2"): True})
    _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/admin/sessions", params={"user_id": "alice"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [item["session_id"] for item in body["data"]] == ["s1"]
    assert audit_sink.events[-1].metadata == {"operation": "list_admin_sessions", "count": 1, "user_id": "alice"}


def test_admin_session_detail_returns_owner_and_runtime_status(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s2", "bob"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("bob", "s2"): True})
    _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/admin/sessions/s2")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["session_id"] == "s2"
    assert body["data"]["owner_user_id"] == "bob"
    assert body["data"]["status"] == "running"
    assert body["data"]["consumer_offset"] == 0
    assert audit_sink.events[-1].metadata["operation"] == "get_admin_session"
    assert audit_sink.events[-1].metadata["old"]["status"] == "running"


def test_admin_session_stop_cancels_running_task_and_audits(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s2", "bob"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("bob", "s2"): True})
    _, asyncio_task = _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.post("/api/v1/admin/sessions/s2/stop")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"session_id": "s2", "stopped": True},
        "errorCode": None,
        "errorMessage": None,
    }
    assert asyncio_task.cancelled is True
    assert audit_sink.events[-1].decision == "allow"
    assert audit_sink.events[-1].metadata["operation"] == "stop_admin_session"
    assert audit_sink.events[-1].metadata["stopped"] is True


def test_admin_session_delete_uses_recorded_owner_scope_and_removes_owner(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True})
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.delete("/api/v1/admin/sessions/s1")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"session_id": "s1", "deleted": True},
        "errorCode": None,
        "errorMessage": None,
    }
    assert svc.chat.delete_calls == [("s1", "alice")]
    assert asyncio.run(owner_store.get_owner("project", "s1")) is None
    assert audit_sink.events[-1].decision == "allow"
    assert audit_sink.events[-1].metadata["operation"] == "delete_admin_session"
    assert audit_sink.events[-1].metadata["old"]["owner_user_id"] == "alice"
    assert audit_sink.events[-1].metadata["new"] == {"deleted": True}


def test_admin_session_routes_register_expected_paths():
    routes = {
        (next(iter(route.methods - {"HEAD", "OPTIONS"})), route.path)
        for route in admin_session_routes.router.routes
        if isinstance(route, APIRoute)
    }

    assert routes == {
        ("DELETE", "/api/v1/admin/sessions/{session_id}"),
        ("GET", "/api/v1/admin/sessions"),
        ("GET", "/api/v1/admin/sessions/{session_id}"),
        ("POST", "/api/v1/admin/sessions/{session_id}/stop"),
    }

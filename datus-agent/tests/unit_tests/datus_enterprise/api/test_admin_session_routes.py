import asyncio
from types import SimpleNamespace

import pytest
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


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


class DummyAsyncioTask:
    def __init__(self):
        self.cancelled = False

    def done(self):
        return False

    def cancel(self):
        self.cancelled = True


class CompletedAsyncioTask:
    def done(self):
        return True

    def cancel(self):
        return None


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


class FailingOwnerStore(InMemorySessionOwnerStore):
    async def get_owner(self, project_id, session_id):
        raise RuntimeError("owner store down")


class DeleteFailingOwnerStore(InMemorySessionOwnerStore):
    async def delete_owner(self, project_id, session_id):
        raise RuntimeError("owner delete down")


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

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
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


def _add_completed_task(manager, session_id, owner_user_id):
    task = ChatTask(session_id=session_id, asyncio_task=CompletedAsyncioTask(), owner_user_id=owner_user_id)
    task.status = "completed"
    manager._completed_tasks[session_id] = task
    return task


def test_admin_sessions_rejects_without_permission(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.datasources"})

    with _client(ctx, _svc()) as client:
        response = client.get("/api/v1/admin/sessions")

    assert response.status_code == 403
    assert "module.admin.sessions" in response.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/admin/sessions"),
        ("get", "/api/v1/admin/sessions/s1"),
        ("post", "/api/v1/admin/sessions/s1/stop"),
        ("delete", "/api/v1/admin/sessions/s1"),
    ],
)
def test_admin_sessions_rbac_denial_does_not_resolve_datus_service(monkeypatch, method, path):
    owner_store = InMemorySessionOwnerStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_session_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = getattr(client, method)(path)

    assert response.status_code == 403


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


@pytest.mark.parametrize(
    ("method", "path", "operation"),
    [
        ("get", "/api/v1/admin/sessions/s2", "get_admin_session"),
        ("post", "/api/v1/admin/sessions/s2/stop", "stop_admin_session"),
        ("delete", "/api/v1/admin/sessions/s2", "delete_admin_session"),
    ],
)
def test_admin_session_read_failure_returns_stable_error(monkeypatch, method, path, operation):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, FailingOwnerStore(), audit_sink)
    svc = _svc(existing={("bob", "s2"): True})
    _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = getattr(client, method)(path)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SESSION_READ_FAILED"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "session read failed"
    assert audit_sink.events[-1].metadata["operation"] == operation
    assert svc.chat.delete_calls == []


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


@pytest.mark.asyncio
async def test_admin_session_stop_returns_success_when_post_stop_audit_fails(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    await owner_store.set_owner("project", "s2", "bob")
    _install_extensions(monkeypatch, owner_store, FailingAuditSink())
    svc = _svc(existing={("bob", "s2"): True})
    _, asyncio_task = _add_running_task(svc.task_manager, "s2", "bob")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    result = await admin_session_routes.stop_admin_session("s2", svc, ctx)

    assert result.success is True
    assert result.data == {"session_id": "s2", "stopped": True}
    assert asyncio_task.cancelled is True


def test_admin_session_stop_not_running_audits_deny_noop(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True})
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.post("/api/v1/admin/sessions/s1/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SESSION_NOT_RUNNING"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "session not running"
    assert audit_sink.events[-1].metadata["stopped"] is False


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


@pytest.mark.asyncio
async def test_admin_session_delete_returns_success_when_post_delete_audit_fails(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    await owner_store.set_owner("project", "s1", "alice")
    _install_extensions(monkeypatch, owner_store, FailingAuditSink())
    svc = _svc(existing={("alice", "s1"): True})
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    result = await admin_session_routes.delete_admin_session("s1", svc, ctx)

    assert result.success is True
    assert result.data == {"session_id": "s1", "deleted": True}
    assert svc.chat.delete_calls == [("s1", "alice")]
    assert await owner_store.get_owner("project", "s1") is None


def test_admin_session_delete_owner_store_failure_returns_stable_error(monkeypatch):
    owner_store = DeleteFailingOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True})
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.delete("/api/v1/admin/sessions/s1")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SESSION_OWNER_DELETE_FAILED"
    assert body["errorMessage"] == "Session owner metadata delete failed."
    assert svc.chat.delete_calls == [("s1", "alice")]
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "session owner delete failed"
    assert audit_sink.events[-1].metadata["operation"] == "delete_admin_session"
    assert audit_sink.events[-1].metadata["old"]["owner_user_id"] == "alice"


def test_admin_session_delete_removes_completed_task_snapshot(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "s1", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={("alice", "s1"): True})
    _add_completed_task(svc.task_manager, "s1", "alice")
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        delete_response = client.delete("/api/v1/admin/sessions/s1")
        list_response = client.get("/api/v1/admin/sessions")
        detail_response = client.get("/api/v1/admin/sessions/s1")

    assert delete_response.status_code == 200
    assert list_response.json()["data"] == []
    assert detail_response.json()["success"] is False
    assert detail_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"


def test_admin_session_delete_rejects_task_without_known_owner(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={(None, "orphan"): True})
    _add_completed_task(svc.task_manager, "orphan", None)
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.delete("/api/v1/admin/sessions/orphan")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SESSION_OWNER_UNKNOWN"
    assert svc.chat.delete_calls == []
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "session owner unknown"
    assert audit_sink.events[-1].metadata["operation"] == "delete_admin_session"
    assert audit_sink.events[-1].metadata["old"]["owner_user_id"] is None


def test_admin_sessions_list_handles_invalid_owner_record_session_id(monkeypatch):
    owner_store = InMemorySessionOwnerStore()
    asyncio.run(owner_store.set_owner("project", "bad/session", "alice"))
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, owner_store, audit_sink)
    svc = _svc(existing={})
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/admin/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["session_id"] == "bad/session"
    assert body["data"][0]["exists_on_disk"] is False


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

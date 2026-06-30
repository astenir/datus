import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import AccessDecision
from datus.api.service import create_app
from datus.api.services.dashboard_service import DashboardService
from datus.api.services.report_service import ReportService
from datus_enterprise.api import artifact_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):  # noqa: ARG002
        raise RuntimeError("audit down")


class MemoryArtifactAclStore:
    def __init__(self, initial=None):
        self.acls = dict(initial or {})

    async def get_acl(self, *, artifact_type: str, slug: str):
        key = (artifact_type, slug)
        if key not in self.acls:
            raise KeyError(key)
        return dict(self.acls[key])

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict):
        self.acls[(artifact_type, slug)] = dict(acl)
        return dict(acl)


class DenyAdminArtifactsAuthorizationProvider(LocalAuthorizationProvider):
    async def check(self, ctx, action, resource):
        if action == "module.admin.artifacts":
            return AccessDecision(allowed=False, reason="admin artifacts denied")
        return await super().check(ctx, action, resource)


def _svc(tmp_path: Path):
    agent_config = SimpleNamespace(project_root=str(tmp_path))
    return SimpleNamespace(
        agent_config=agent_config,
        dashboard=DashboardService(agent_config=agent_config),
        report=ReportService(agent_config=agent_config),
    )


def _write_manifest(root: Path, kind: str, slug: str) -> None:
    base = root / f"{kind}s" / slug
    (base / "render").mkdir(parents=True, exist_ok=True)
    (base / "render" / "app.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
    (base / "manifest.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "name": slug,
                "description": "Test artifact",
                "kind": kind,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def _override_app_context(app: FastAPI, ctx: AppContext) -> None:
    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_request_app_context] = override_context


def _client(
    monkeypatch,
    tmp_path: Path,
    ctx: AppContext,
    *,
    audit_sink=None,
    artifact_acl_store=None,
    user_store=None,
    role_store=None,
) -> TestClient:
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc(tmp_path)

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            artifact_acl_store=artifact_acl_store,
            user_store=user_store or InMemoryEnterpriseUserStore(),
            role_store=role_store or InMemoryEnterpriseRoleStore(),
        ),
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "permissions", "json_body"),
    [
        ("get", "/api/v1/dashboards", {"module.report.view"}, None),
        ("get", "/api/v1/dashboards/sales", {"module.report.view"}, None),
        ("get", "/api/v1/dashboards/sales/acl", {"module.report.view"}, None),
        (
            "put",
            "/api/v1/dashboards/sales/acl",
            {"module.report.view"},
            {"visibility": "private", "allowed_roles": [], "allowed_user_ids": []},
        ),
        ("get", "/api/v1/dashboards/sales/html", {"module.report.view"}, None),
        ("get", "/api/v1/reports", {"module.dashboard.view"}, None),
        ("get", "/api/v1/reports/sales", {"module.dashboard.view"}, None),
        ("get", "/api/v1/reports/sales/acl", {"module.dashboard.view"}, None),
        (
            "put",
            "/api/v1/reports/sales/acl",
            {"module.dashboard.view"},
            {"visibility": "private", "allowed_roles": [], "allowed_user_ids": []},
        ),
        ("get", "/api/v1/reports/sales/html", {"module.dashboard.view"}, None),
        ("get", "/api/v1/admin/artifacts", {"module.report.view"}, None),
        ("get", "/api/v1/admin/artifacts/report/sales/acl", {"module.report.view"}, None),
        (
            "put",
            "/api/v1/admin/artifacts/report/sales/acl",
            {"module.report.view"},
            {
                "owner_user_id": "u1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            },
        ),
    ],
)
def test_artifact_rbac_denial_does_not_resolve_datus_service(monkeypatch, method, path, permissions, json_body):
    ctx = AppContext(user_id="u1", permissions=permissions)
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("path", "permissions"),
    [
        ("/api/v1/dashboards/sales/acl", {"module.dashboard.view"}),
        ("/api/v1/reports/sales/acl", {"module.report.view"}),
        ("/api/v1/admin/artifacts/report/sales/acl", {"module.admin.artifacts"}),
    ],
)
def test_artifact_invalid_body_does_not_resolve_datus_service(monkeypatch, path, permissions):
    ctx = AppContext(user_id="u1", permissions=permissions)
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.put(path, json=[])

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_list_filters_through_enterprise_acl(tmp_path: Path):
    _write_manifest(tmp_path, "report", "visible")
    _write_manifest(tmp_path, "report", "hidden")
    ctx = AppContext(principal={"artifact_acl": {"report": ["visible"]}})

    result = await artifact_routes.list_reports(_svc(tmp_path), ctx)

    assert result.success is True
    assert [item.slug for item in result.data] == ["visible"]


@pytest.mark.asyncio
async def test_report_list_uses_configured_acl_store_without_principal_fallback(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "visible")
    store = MemoryArtifactAclStore(
        {
            ("report", "visible"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(
        user_id="viewer-1",
        permissions={"module.report.view"},
        principal={"artifact_acl": {"report": ["visible"]}},
    )
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            artifact_acl_store=store,
        ),
    )

    result = await artifact_routes.list_reports(_svc(tmp_path), ctx)

    assert result.success is True
    assert result.data == []


@pytest.mark.asyncio
async def test_dashboard_list_admin_visibility_uses_authorization_provider(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "ops")
    store = MemoryArtifactAclStore(
        {
            ("dashboard", "ops"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="admin", permissions={"module.dashboard.view", "module.admin.artifacts"})
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=DenyAdminArtifactsAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            artifact_acl_store=store,
        ),
    )

    result = await artifact_routes.list_dashboards(_svc(tmp_path), ctx)

    assert result.success is True
    assert result.data == []


@pytest.mark.asyncio
async def test_dashboard_list_filters_through_enterprise_acl(tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "visible")
    _write_manifest(tmp_path, "dashboard", "hidden")
    ctx = AppContext(principal={"artifact_acl": {"dashboard": ["hidden"]}})

    result = await artifact_routes.list_dashboards(_svc(tmp_path), ctx)

    assert result.success is True
    assert [item.slug for item in result.data] == ["hidden"]


def test_admin_artifacts_lists_all_manifests_and_audits(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "visible_report")
    _write_manifest(tmp_path, "report", "hidden_report")
    _write_manifest(tmp_path, "dashboard", "hidden_dashboard")
    audit_sink = CollectingAuditSink()
    ctx = AppContext(
        user_id="u1",
        permissions={"module.admin.artifacts"},
        principal={"artifact_acl": {"report": ["visible_report"], "dashboard": []}},
    )
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc(tmp_path)

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
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

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    listed = {(item["artifact_type"], item["manifest"]["slug"]) for item in body["data"]}
    assert listed == {
        ("report", "visible_report"),
        ("report", "hidden_report"),
        ("dashboard", "hidden_dashboard"),
    }
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "module.admin.artifacts"
    assert event.resource_type == "artifact"
    assert event.resource_id is None
    assert event.decision == "allow"
    assert event.metadata == {"operation": "list_admin_artifacts", "count": 3}


def test_admin_artifacts_list_survives_audit_failure(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "visible_report")
    _write_manifest(tmp_path, "dashboard", "visible_dashboard")
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc(tmp_path)

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/admin/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    listed = {(item["artifact_type"], item["manifest"]["slug"]) for item in body["data"]}
    assert listed == {("report", "visible_report"), ("dashboard", "visible_dashboard")}


def test_get_admin_artifact_acl_returns_unavailable_without_store(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink) as client:
        response = client.get("/api/v1/admin/artifacts/report/sales/acl")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "ARTIFACT_ACL_UNAVAILABLE"
    event = audit_sink.events[-1]
    assert event.action == "module.admin.artifacts"
    assert event.resource_type == "artifact_acl"
    assert event.resource_id == "report:sales"
    assert event.decision == "deny"
    assert event.reason == "artifact ACL store unavailable"
    assert event.metadata == {"operation": "get_artifact_acl"}


def test_get_admin_artifact_acl_returns_stored_acl_and_audits(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "ops")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("dashboard", "ops"): {
                "owner_user_id": "owner-1",
                "visibility": "role",
                "allowed_roles": ["analyst"],
                "allowed_user_ids": ["viewer-1"],
                "datasources": ["finance_dw"],
            }
        }
    )
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.get("/api/v1/admin/artifacts/dashboard/ops/acl")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "owner_user_id": "owner-1",
        "visibility": "role",
        "allowed_roles": ["analyst"],
        "allowed_user_ids": ["viewer-1"],
        "datasources": ["finance_dw"],
    }
    event = audit_sink.events[-1]
    assert event.resource_id == "dashboard:ops"
    assert event.decision == "allow"
    assert event.metadata == {"operation": "get_artifact_acl"}


def test_get_admin_artifact_acl_returns_not_found_for_missing_acl(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore()
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.get("/api/v1/admin/artifacts/report/sales/acl")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "ARTIFACT_ACL_NOT_FOUND"
    event = audit_sink.events[-1]
    assert event.resource_id == "report:sales"
    assert event.decision == "deny"
    assert event.reason == "artifact ACL not found"


def test_put_admin_artifact_acl_updates_store_and_audits_summary(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "old-owner",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})
    payload = {
        "owner_user_id": "new-owner",
        "visibility": "enterprise",
        "allowed_roles": ["analyst", "lead"],
        "allowed_user_ids": ["viewer-1"],
        "datasources": ["finance_dw"],
    }

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.put("/api/v1/admin/artifacts/report/sales/acl", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == payload
    assert store.acls[("report", "sales")] == payload
    event = audit_sink.events[-1]
    assert event.resource_id == "report:sales"
    assert event.decision == "allow"
    assert event.metadata == {
        "operation": "put_artifact_acl",
        "old_acl": {
            "owner_user_id": "old-owner",
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": [],
            "datasources": [],
        },
        "new_acl": {
            "owner_user_id": "new-owner",
            "visibility": "enterprise",
            "allowed_roles": ["analyst", "lead"],
            "allowed_user_ids": ["viewer-1"],
            "datasources": ["finance_dw"],
        },
    }


def test_put_admin_artifact_acl_returns_success_when_post_update_audit_fails(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "old-owner",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})
    payload = {
        "owner_user_id": "new-owner",
        "visibility": "enterprise",
        "allowed_roles": ["analyst"],
        "allowed_user_ids": ["viewer-1"],
        "datasources": ["finance_dw"],
    }

    with _client(monkeypatch, tmp_path, ctx, audit_sink=FailingAuditSink(), artifact_acl_store=store) as client:
        response = client.put("/api/v1/admin/artifacts/report/sales/acl", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == payload
    assert store.acls[("report", "sales")] == payload


def test_put_admin_artifact_acl_creates_first_acl_for_existing_artifact(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "ops")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore()
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})
    payload = {
        "owner_user_id": "owner-1",
        "visibility": "private",
        "allowed_roles": [],
        "allowed_user_ids": [],
        "datasources": [],
    }

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.put("/api/v1/admin/artifacts/dashboard/ops/acl", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert store.acls[("dashboard", "ops")] == payload
    assert audit_sink.events[-1].metadata["old_acl"] == {}


def test_put_admin_artifact_acl_changes_runtime_report_visibility(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore()
    ctx_holder = {"ctx": AppContext(user_id="admin", permissions={"module.admin.artifacts"})}
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx_holder["ctx"]
        return _svc(tmp_path)

    async def override_context(request: Request):
        request.state.app_context = ctx_holder["ctx"]
        return ctx_holder["ctx"]

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            artifact_acl_store=store,
        ),
    )

    with TestClient(app) as client:
        put_response = client.put(
            "/api/v1/admin/artifacts/report/sales/acl",
            json={
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            },
        )
        assert put_response.json()["success"] is True

        ctx_holder["ctx"] = AppContext(user_id="viewer-1", permissions={"module.report.view"})
        viewer_response = client.get("/api/v1/reports")
        assert viewer_response.json()["success"] is True
        assert viewer_response.json()["data"] == []

        ctx_holder["ctx"] = AppContext(user_id="owner-1", permissions={"module.report.view"})
        owner_response = client.get("/api/v1/reports")
        assert owner_response.json()["success"] is True
        assert [item["slug"] for item in owner_response.json()["data"]] == ["sales"]


def test_artifact_share_user_directory_returns_sanitized_enabled_users(monkeypatch, tmp_path: Path):
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()

    async def seed_users():
        await user_store.upsert_user(
            user_id="owner-1",
            display_name="Owner User",
            email="owner@example.com",
            department="Finance",
            title="Analyst",
        )
        await user_store.upsert_user(
            user_id="viewer-1",
            display_name="Viewer One",
            email="viewer@example.com",
            department="Finance",
            title="Reviewer",
        )
        await user_store.upsert_user(
            user_id="disabled-1",
            display_name="Disabled Viewer",
            email="disabled@example.com",
            enabled=False,
        )

    asyncio.run(seed_users())
    ctx = AppContext(user_id="owner-1", permissions={"module.report.view"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, user_store=user_store) as client:
        response = client.get(
            "/api/v1/artifact-share/users",
            params={"artifact_type": "report", "query": "view"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == [
        {
            "user_id": "viewer-1",
            "display_name": "Viewer One",
            "email": "viewer@example.com",
            "department": "Finance",
            "title": "Reviewer",
        }
    ]
    assert "role_ids" not in body["data"][0]
    assert audit_sink.events[-1].action == "artifact.share.lookup"
    assert audit_sink.events[-1].resource_id == "report:user"
    assert audit_sink.events[-1].decision == "allow"
    assert audit_sink.events[-1].metadata["count"] == 1


def test_artifact_share_role_directory_hides_permissions(monkeypatch, tmp_path: Path):
    role_store = InMemoryEnterpriseRoleStore()

    async def seed_roles():
        await role_store.upsert_role(
            role_id="analyst",
            name="Analyst",
            description="Data analyst",
            permissions=["module.sql_executor", "module.admin.users"],
        )
        await role_store.upsert_role(role_id="viewer", name="Viewer", description="Read-only")

    asyncio.run(seed_roles())
    ctx = AppContext(user_id="owner-1", permissions={"module.dashboard.view"})

    with _client(monkeypatch, tmp_path, ctx, role_store=role_store) as client:
        response = client.get(
            "/api/v1/artifact-share/roles",
            params={"artifact_type": "dashboard", "query": "ana"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == [
        {
            "role_id": "analyst",
            "name": "Analyst",
            "description": "Data analyst",
            "built_in": False,
        }
    ]
    assert "permissions" not in body["data"][0]


def test_artifact_share_directory_requires_matching_view_permission(monkeypatch, tmp_path: Path):
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="owner-1", permissions={"module.report.view"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink) as client:
        response = client.get(
            "/api/v1/artifact-share/users",
            params={"artifact_type": "dashboard"},
        )

    assert response.status_code == 403
    assert "module.dashboard.view" in response.json()["detail"]
    assert audit_sink.events[-1].action == "artifact.share.lookup"
    assert audit_sink.events[-1].resource_id == "dashboard:user"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].metadata["required_permission"] == "module.dashboard.view"


def test_creator_can_share_report_with_single_user(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": ["finance_dw"],
            }
        }
    )
    ctx_holder = {"ctx": AppContext(user_id="owner-1", permissions={"module.report.view"})}
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx_holder["ctx"]
        return _svc(tmp_path)

    async def override_context(request: Request):
        request.state.app_context = ctx_holder["ctx"]
        return ctx_holder["ctx"]

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            artifact_acl_store=store,
        ),
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/reports/sales/acl",
            json={"visibility": "private", "allowed_roles": [], "allowed_user_ids": ["viewer-1"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == {
            "owner_user_id": "owner-1",
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": ["viewer-1"],
        }
        assert store.acls[("report", "sales")] == {
            "owner_user_id": "owner-1",
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": ["viewer-1"],
            "datasources": ["finance_dw"],
        }

        ctx_holder["ctx"] = AppContext(user_id="viewer-1", permissions={"module.report.view"})
        list_response = client.get("/api/v1/reports")
        assert [item["slug"] for item in list_response.json()["data"]] == ["sales"]
        detail_response = client.get("/api/v1/reports/sales")
        assert detail_response.json()["success"] is True

    event = next(
        event
        for event in audit_sink.events
        if event.action == "artifact.share" and event.resource_id == "report:sales" and event.decision == "allow"
    )
    assert event.action == "artifact.share"
    assert event.resource_id == "report:sales"
    assert event.decision == "allow"
    assert event.metadata["new_acl"]["allowed_user_ids"] == ["viewer-1"]
    assert event.metadata["new_acl"]["datasources"] == ["finance_dw"]


def test_creator_share_returns_success_when_post_update_audit_fails(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": ["finance_dw"],
            }
        }
    )
    ctx = AppContext(user_id="owner-1", permissions={"module.report.view"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=FailingAuditSink(), artifact_acl_store=store) as client:
        response = client.put(
            "/api/v1/reports/sales/acl",
            json={"visibility": "private", "allowed_roles": [], "allowed_user_ids": ["viewer-1"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["allowed_user_ids"] == ["viewer-1"]
    assert store.acls[("report", "sales")] == {
        "owner_user_id": "owner-1",
        "visibility": "private",
        "allowed_roles": [],
        "allowed_user_ids": ["viewer-1"],
        "datasources": ["finance_dw"],
    }


def test_non_owner_shared_user_cannot_update_report_share(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": ["viewer-1"],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="viewer-1", permissions={"module.report.view"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.put(
            "/api/v1/reports/sales/acl",
            json={"visibility": "enterprise", "allowed_roles": [], "allowed_user_ids": []},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "ARTIFACT_FORBIDDEN"
    assert store.acls[("report", "sales")]["visibility"] == "private"
    event = audit_sink.events[-1]
    assert event.action == "artifact.share"
    assert event.resource_id == "report:sales"
    assert event.decision == "deny"
    assert event.reason == "artifact owner required"


def test_is_admin_without_admin_artifacts_cannot_update_report_share(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "report", "sales")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("report", "sales"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="admin-1", is_admin=True, permissions={"module.report.view"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.put(
            "/api/v1/reports/sales/acl",
            json={"visibility": "enterprise", "allowed_roles": [], "allowed_user_ids": []},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "ARTIFACT_FORBIDDEN"
    assert store.acls[("report", "sales")]["visibility"] == "private"
    event = audit_sink.events[-1]
    assert event.action == "artifact.share"
    assert event.resource_id == "report:sales"
    assert event.decision == "deny"
    assert event.reason == "artifact owner required"


def test_admin_artifacts_permission_can_update_dashboard_share(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "ops")
    store = MemoryArtifactAclStore(
        {
            ("dashboard", "ops"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="admin", permissions={"module.dashboard.view", "module.admin.artifacts"})

    with _client(monkeypatch, tmp_path, ctx, artifact_acl_store=store) as client:
        response = client.put(
            "/api/v1/dashboards/ops/acl",
            json={
                "visibility": "role",
                "allowed_roles": ["analyst", "analyst"],
                "allowed_user_ids": ["viewer-1", "viewer-1"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "owner_user_id": "owner-1",
        "visibility": "role",
        "allowed_roles": ["analyst"],
        "allowed_user_ids": ["viewer-1"],
    }
    assert store.acls[("dashboard", "ops")] == {
        "owner_user_id": "owner-1",
        "visibility": "role",
        "allowed_roles": ["analyst"],
        "allowed_user_ids": ["viewer-1"],
        "datasources": [],
    }


def test_admin_artifacts_share_management_uses_authorization_provider(monkeypatch, tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "ops")
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore(
        {
            ("dashboard", "ops"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            }
        }
    )
    ctx = AppContext(user_id="admin", permissions={"module.dashboard.view", "module.admin.artifacts"})
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc(tmp_path)

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=DenyAdminArtifactsAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            artifact_acl_store=store,
        ),
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/dashboards/ops/acl",
            json={"visibility": "enterprise", "allowed_roles": [], "allowed_user_ids": []},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "ARTIFACT_FORBIDDEN"
    assert store.acls[("dashboard", "ops")]["visibility"] == "private"
    assert audit_sink.events[-1].action == "artifact.share"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "artifact owner required"


def test_put_admin_artifact_acl_rejects_missing_artifact_before_store_write(monkeypatch, tmp_path: Path):
    audit_sink = CollectingAuditSink()
    store = MemoryArtifactAclStore()
    ctx = AppContext(user_id="u1", permissions={"module.admin.artifacts"})

    with _client(monkeypatch, tmp_path, ctx, audit_sink=audit_sink, artifact_acl_store=store) as client:
        response = client.put(
            "/api/v1/admin/artifacts/report/missing/acl",
            json={
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "allowed_user_ids": [],
                "datasources": [],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "RESOURCE_NOT_FOUND"
    assert store.acls == {}
    event = audit_sink.events[-1]
    assert event.resource_id == "report:missing"
    assert event.decision == "deny"
    assert event.reason == "artifact not found"


def test_admin_artifacts_rejects_without_admin_artifacts(monkeypatch, tmp_path: Path):
    ctx = AppContext(permissions={"module.report.view"})
    app = FastAPI()
    app.include_router(artifact_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc(tmp_path)

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/artifacts")

    assert response.status_code == 403
    assert "module.admin.artifacts" in response.json()["detail"]


def test_enterprise_artifact_routes_expose_resource_paths_only():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/admin/artifacts" in route_paths
    assert "/api/v1/admin/artifacts/{artifact_type}/{slug}/acl" in route_paths
    assert "/api/v1/artifact-share/users" in route_paths
    assert "/api/v1/artifact-share/roles" in route_paths
    assert "/api/v1/reports" in route_paths
    assert "/api/v1/reports/{slug}/acl" in route_paths
    assert "/api/v1/reports/{slug}/html" in route_paths
    assert "/api/v1/dashboards" in route_paths
    assert "/api/v1/dashboards/{slug}/acl" in route_paths
    assert "/api/v1/dashboards/{slug}/html" in route_paths
    assert "/api/v1/report/list" not in route_paths
    assert "/api/v1/report/html" not in route_paths
    assert "/api/v1/dashboard/list" not in route_paths
    assert "/api/v1/dashboard/html" not in route_paths

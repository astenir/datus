import pytest
from fastapi import HTTPException
from starlette.datastructures import State

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    PassthroughConfigProjector,
)
from datus.api.enterprise.deps import (
    authorize_session_access,
    enforce_platform_status,
    project_request_config,
    reject_in_enterprise_mode,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import AccessDecision, ProjectionResult
from datus_enterprise.authorization import authorize, require_module


@pytest.mark.asyncio
async def test_local_authorization_allows_when_permissions_absent():
    decision = await authorize(AppContext(), action="module.dashboard.view")

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_local_authorization_checks_explicit_permissions():
    ctx = AppContext(principal={"permissions": ["module.report.*"]})

    allowed = await authorize(ctx, action="module.report.view")
    denied = await authorize(ctx, action="module.dashboard.view")

    assert allowed.allowed is True
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_require_module_raises_403_for_missing_permission():
    dependency = require_module("module.config.edit")
    ctx = AppContext(principal={"permissions": ["module.report.view"]})
    request = type("Request", (), {})()
    request.state = State()
    request.state.app_context = ctx

    with pytest.raises(HTTPException) as exc:
        await dependency(request)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_module_uses_authorization_provider_for_identity_only_context(monkeypatch):
    class FakeAuthorizationProvider:
        async def check(self, ctx, action, resource):
            return AccessDecision(allowed=action == "module.config.edit", reason=f"checked {ctx.user_id}")

        async def allowed_datasources(self, ctx):  # noqa: ARG002
            return {}

    class CollectingAuditSink:
        def __init__(self):
            self.events = []

        async def write(self, event):
            self.events.append(event)

    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=FakeAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
        ),
    )

    request = type("Request", (), {})()
    request.state = State()
    request.state.app_context = AppContext(user_id="u1")

    allowed_dependency = require_module("module.config.edit")
    denied_dependency = require_module("module.admin.users")

    assert await allowed_dependency(request) == request.state.app_context
    with pytest.raises(HTTPException) as exc:
        await denied_dependency(request)

    assert exc.value.status_code == 403
    assert audit_sink.events[-1].user_id == "u1"
    assert audit_sink.events[-1].action == "module.admin.users"


@pytest.mark.asyncio
async def test_require_module_denial_stays_stable_when_audit_sink_fails(monkeypatch):
    class DenyingAuthorizationProvider:
        async def check(self, ctx, action, resource):  # noqa: ARG002
            return AccessDecision(allowed=False, reason="missing permission module.admin.users")

        async def allowed_datasources(self, ctx):  # noqa: ARG002
            return {}

    class FailingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise RuntimeError("audit down")

    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=DenyingAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )

    request = type("Request", (), {})()
    request.state = State()
    request.state.app_context = AppContext(user_id="u1")

    dependency = require_module("module.admin.users")

    with pytest.raises(HTTPException) as exc:
        await dependency(request)

    assert exc.value.status_code == 403
    assert exc.value.detail == "missing permission module.admin.users"


@pytest.mark.asyncio
async def test_project_request_config_denial_stays_stable_when_audit_sink_fails(monkeypatch):
    class DenyingConfigProjector:
        async def project(self, request):
            return ProjectionResult(
                config=request.base_config,
                denied_reason="No datasource grant available.",
            )

    class UnusedAuthorizationProvider:
        async def check(self, ctx, action, resource):  # noqa: ARG002
            return AccessDecision(allowed=True)

        async def allowed_datasources(self, ctx):  # noqa: ARG002
            return {}

    class FailingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise RuntimeError("audit down")

    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=UnusedAuthorizationProvider(),
            config_projector=DenyingConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await project_request_config(
            AppContext(user_id="u1"),
            object(),
            operation="sql.query",
            requested_datasource="finance",
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "No datasource grant available."


@pytest.mark.asyncio
async def test_platform_status_denial_stays_stable_when_audit_sink_fails(monkeypatch):
    class FailingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise RuntimeError("audit down")

    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await enforce_platform_status(
            AppContext(user_id="u1"),
            operation="session.delete",
            resource_type="session",
            resource_id="s1",
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "PLATFORM_STATUS_FORBIDDEN"


@pytest.mark.asyncio
async def test_enterprise_route_disabled_stays_stable_when_audit_sink_fails(monkeypatch):
    class FailingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise RuntimeError("audit down")

    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await reject_in_enterprise_mode(
            AppContext(user_id="u1"),
            operation="legacy.model.delete",
            resource_type="legacy_api",
            resource_id="/api/v1/model",
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "ENTERPRISE_ROUTE_DISABLED"


@pytest.mark.asyncio
async def test_session_access_denial_stays_stable_when_audit_sink_fails(monkeypatch):
    class FailingOwnerStore(InMemorySessionOwnerStore):
        async def get_owner(self, project_id, session_id):  # noqa: ARG002
            raise RuntimeError("owner store down")

    class FailingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise RuntimeError("audit down")

    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=FailingOwnerStore(),
            audit_sink=FailingAuditSink(),
        ),
    )
    svc = type("Service", (), {})()
    svc.project_id = "project-1"
    svc.task_manager = type("TaskManager", (), {"get_task": lambda self, session_id: None})()

    access = await authorize_session_access(
        svc,
        AppContext(user_id="u1"),
        "s1",
        action="history",
        require_existing_session=True,
    )

    assert access.error.errorCode == "RESOURCE_NOT_FOUND"
    assert access.user_id is None


@pytest.mark.asyncio
async def test_require_module_authorizes_without_resolving_datus_service(monkeypatch):
    class FakeAuthorizationProvider:
        async def check(self, ctx, action, resource):
            return AccessDecision(allowed=True, reason=f"checked {ctx.user_id}")

        async def allowed_datasources(self, ctx):  # noqa: ARG002
            return {}

    class CollectingAuditSink:
        async def write(self, event):  # noqa: ARG002
            raise AssertionError("audit should not be written for allowed module access")

    mock_auth = type("Auth", (), {})()
    mock_auth.authenticate = None
    mock_cache = type("Cache", (), {})()
    mock_cache.get_or_create = None
    monkeypatch.setattr(deps, "_auth_provider", mock_auth)
    monkeypatch.setattr(deps, "_service_cache", mock_cache)
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=FakeAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=CollectingAuditSink(),
        ),
    )

    request = type("Request", (), {})()
    request.state = State()
    request.state.app_context = AppContext(user_id="u1")
    request.state.app_context_enterprise_ready = True

    dependency = require_module("module.config.view")

    assert await dependency(request) == request.state.app_context

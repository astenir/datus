import pytest
from fastapi import HTTPException
from starlette.datastructures import State

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import InMemorySessionOwnerStore, PassthroughConfigProjector
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import AccessDecision
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

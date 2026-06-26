import pytest

from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import LocalAuthorizationProvider
from datus.api.enterprise.models import ResourceRef


@pytest.mark.asyncio
async def test_local_authorization_uses_app_context_permissions_first():
    provider = LocalAuthorizationProvider()
    ctx = AppContext(permissions={"module.dashboard.*"}, principal={"permissions": ["module.report.*"]})

    allowed = await provider.check(ctx, "module.dashboard.view", ResourceRef(type="dashboard"))
    denied = await provider.check(ctx, "module.report.view", ResourceRef(type="report"))

    assert allowed.allowed is True
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_local_authorization_keeps_principal_permissions_compatibility():
    provider = LocalAuthorizationProvider()
    ctx = AppContext(principal={"permissions": ["module.report.*"]})

    decision = await provider.check(ctx, "module.report.view", ResourceRef(type="report"))

    assert decision.allowed is True

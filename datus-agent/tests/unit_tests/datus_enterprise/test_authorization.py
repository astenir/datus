import pytest
from fastapi import HTTPException
from starlette.datastructures import State

from datus.api.auth.context import AppContext
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

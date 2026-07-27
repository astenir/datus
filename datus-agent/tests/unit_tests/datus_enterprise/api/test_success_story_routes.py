# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for the enterprise success-story route."""

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import SessionAccess
from datus.api.models.base_models import Result
from datus.api.models.downstream import SuccessStoryData, SuccessStoryInput, SuccessStorySource
from datus.api.service import create_app
from datus.api.services.chat_service import SuccessStorySourceError
from datus_enterprise.api import success_story_routes


def _payload():
    return SuccessStoryInput(session_id="chat_session_1", call_tool_id="call_1", session_link="/chat/chat_session_1")


def _source(sql="SELECT 1"):
    return SuccessStorySource(
        session_id="chat_session_1",
        call_tool_id="call_1",
        question="show one",
        sql=sql,
        datasource_id="ccks_fund",
        subagent_name="gen_sql",
        session_link="/chat/chat_session_1",
    )


def _data(created=True):
    return SuccessStoryData(
        story_id="ss_123",
        created=created,
        datasource_id="ccks_fund",
        subagent_name="gen_sql",
        storage_key="ccks_fund/gen_sql/success_story.csv",
        session_id="chat_session_1",
        timestamp="2026-04-20T00:00:00Z",
    )


def _svc(source=None, save=None):
    svc = MagicMock()
    svc.chat.resolve_success_story_source_async = AsyncMock(return_value=source or _source())
    svc.success_story.save = save or MagicMock(return_value=_data())
    return svc


def test_create_app_registers_authoritative_success_story_route_once():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/success-stories" and "POST" in getattr(route, "methods", set())
    ]

    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == "datus_enterprise.api.success_story_routes"


async def _install(monkeypatch, svc, access=None):
    monkeypatch.setattr(success_story_routes.api_deps, "resolve_datus_service_for_request", AsyncMock(return_value=svc))
    monkeypatch.setattr(
        success_story_routes,
        "authorize_session_access",
        AsyncMock(return_value=access or SessionAccess(error=None, user_id="alice")),
    )
    monkeypatch.setattr(success_story_routes, "_audit_success_story", AsyncMock())


@pytest.mark.asyncio
async def test_save_returns_canonical_result(monkeypatch):
    svc = _svc()
    await _install(monkeypatch, svc)

    result = await success_story_routes.save_success_story(_payload(), MagicMock(), AppContext(user_id="alice"))

    assert result.success is True
    assert result.data == _data()
    svc.chat.resolve_success_story_source_async.assert_awaited_once_with(
        "chat_session_1",
        "call_1",
        user_id="alice",
        session_link="/chat/chat_session_1",
    )
    svc.success_story.save.assert_called_once_with(_source())


@pytest.mark.asyncio
async def test_foreign_session_returns_stable_error(monkeypatch):
    svc = _svc()
    denial = Result[dict](success=False, errorCode="SESSION_FORBIDDEN", errorMessage="denied")
    await _install(monkeypatch, svc, SessionAccess(error=denial, user_id=None))

    result = await success_story_routes.save_success_story(_payload(), MagicMock(), AppContext(user_id="alice"))

    assert result.success is False
    assert result.errorCode == "SUCCESS_STORY_SESSION_FORBIDDEN"
    svc.chat.resolve_success_story_source_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_or_failed_source_returns_resolver_code(monkeypatch):
    svc = _svc()
    svc.chat.resolve_success_story_source_async.side_effect = SuccessStorySourceError(
        "SUCCESS_STORY_NOT_SUCCESSFUL",
        "Only successful SQL can be saved.",
    )
    await _install(monkeypatch, svc)

    result = await success_story_routes.save_success_story(_payload(), MagicMock(), AppContext(user_id="alice"))

    assert result.success is False
    assert result.errorCode == "SUCCESS_STORY_NOT_SUCCESSFUL"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM users", "CREATE TABLE x (id INT)", "SELECT 1; DELETE FROM users"],
)
async def test_write_sql_is_rejected(monkeypatch, sql):
    svc = _svc(source=_source(sql))
    await _install(monkeypatch, svc)

    result = await success_story_routes.save_success_story(_payload(), MagicMock(), AppContext(user_id="alice"))

    assert result.success is False
    assert result.errorCode == "SUCCESS_STORY_SQL_NOT_READ_ONLY"
    svc.success_story.save.assert_not_called()


@pytest.mark.asyncio
async def test_os_error_returns_safe_copy(monkeypatch):
    svc = _svc(save=MagicMock(side_effect=OSError("/private/path disk full")))
    await _install(monkeypatch, svc)

    result = await success_story_routes.save_success_story(_payload(), MagicMock(), AppContext(user_id="alice"))

    assert result.success is False
    assert result.errorCode == "SUCCESS_STORY_WRITE_FAILED"
    assert "/private/path" not in result.errorMessage


@pytest.mark.asyncio
async def test_audit_omits_full_sql(monkeypatch):
    events = []
    sink = MagicMock()
    sink.write = AsyncMock(side_effect=lambda event: events.append(event))
    monkeypatch.setattr(success_story_routes, "get_audit_sink", lambda: sink)

    await success_story_routes._audit_success_story(
        AppContext(user_id="alice"),
        _payload(),
        decision="allow",
        metadata={"sql_sha256": "abc", "created": True},
    )

    assert events[0].action == "knowledge.success_story.save"
    assert events[0].metadata == {
        "session_id": "chat_session_1",
        "call_tool_id": "call_1",
        "sql_sha256": "abc",
        "created": True,
    }

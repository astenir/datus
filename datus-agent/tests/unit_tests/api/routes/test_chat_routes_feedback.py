# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for POST /api/v1/chat/feedback endpoint."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from datus.api import deps
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseQuotaStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.downstream import FeedbackChatInput, StreamChatInput
from datus.api.routes.chat_routes import stream_chat_feedback
from datus.tools.sql_policy import SqlPolicyConfig


def _build_svc():
    svc = MagicMock()
    svc.agent_config = SimpleNamespace(
        services=SimpleNamespace(
            datasources={
                "finance": SimpleNamespace(type="sqlite"),
                "hr": SimpleNamespace(type="sqlite"),
            },
            default_datasource=None,
        ),
        current_datasource="finance",
        principal={},
        sql_policy_config=None,
    )
    svc.task_manager.get_task.return_value = None
    svc.chat.session_exists.return_value = True
    svc.chat.session_exists_async = AsyncMock(return_value=True)

    async def _empty_stream(*args, **kwargs):
        if False:
            yield
        return

    svc.chat.stream_chat = MagicMock(side_effect=_empty_stream)
    return svc


def _build_ctx(user_id="tester", datasource_grants=None):
    ctx = MagicMock()
    ctx.user_id = user_id
    ctx.principal = {}
    ctx.datasource_grants = datasource_grants or {}
    return ctx


def _request_with_service(svc):
    async def override_service(request):
        return svc

    return SimpleNamespace(app=SimpleNamespace(dependency_overrides={deps.get_datus_service: override_service}))


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _enterprise_extensions(config_projector=None, audit_sink=None, quota_store=None) -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=config_projector or PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
        quota_store=quota_store or InMemoryEnterpriseQuotaStore(),
    )


async def _drain(response):
    """Iterate a StreamingResponse body_iterator so the inner generator runs."""
    async for _ in response.body_iterator:
        pass


@pytest.mark.asyncio
async def test_feedback_endpoint_renders_prompt_and_routes_to_feedback_subagent():
    svc = _build_svc()
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
        database="sales_db",
    )

    response = await stream_chat_feedback(request, _build_ctx(), _request_with_service(svc))
    await _drain(response)

    svc.chat.stream_chat.assert_called_once()
    call_args = svc.chat.stream_chat.call_args
    stream_input: StreamChatInput = call_args.args[0]
    assert isinstance(stream_input, StreamChatInput)
    assert stream_input.subagent_id == "feedback"
    assert stream_input.source_session_id == "chat_session_abc"
    assert stream_input.database == "sales_db"
    assert call_args.kwargs["sub_agent_id"] == "feedback"
    assert call_args.kwargs["user_id"] == "tester"
    assert stream_input.message == '[The user reacted to this message "Here is your SQL result" with [thumbsup]]'


@pytest.mark.parametrize(
    "field",
    ["source_session_id", "reaction_emoji", "reference_msg"],
)
@pytest.mark.parametrize("blank_value", ["", "   ", "\t\n"])
def test_feedback_input_rejects_blank_required_field(field, blank_value):
    """Required feedback fields must reject empty / whitespace-only strings."""
    kwargs = dict(
        source_session_id="sess_1",
        reaction_emoji="thumbsup",
        reference_msg="hi",
    )
    kwargs[field] = blank_value
    with pytest.raises(ValueError):
        FeedbackChatInput(**kwargs)


def test_feedback_input_strips_whitespace_on_required_fields():
    """Surrounding whitespace on required fields should be stripped, not retained."""
    inp = FeedbackChatInput(
        source_session_id="  sess_1  ",
        reaction_emoji="  thumbsup  ",
        reference_msg="  hi  ",
    )
    assert inp.source_session_id == "sess_1"
    assert inp.reaction_emoji == "thumbsup"
    assert inp.reference_msg == "hi"


@pytest.mark.asyncio
async def test_feedback_endpoint_appends_optional_reaction_msg():
    svc = _build_svc()
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsdown",
        reference_msg="Wrong answer",
        reaction_msg="Please recheck the metric definition",
    )

    response = await stream_chat_feedback(request, _build_ctx(), _request_with_service(svc))
    await _drain(response)

    stream_input: StreamChatInput = svc.chat.stream_chat.call_args.args[0]
    assert stream_input.message.endswith("Please recheck the metric definition")
    assert "[thumbsdown]" in stream_input.message


@pytest.mark.asyncio
async def test_feedback_endpoint_denies_when_sql_policy_enabled_without_principal(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = _build_svc()
    svc.agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
        {
            "enabled": True,
            "provider": "x:Y",
            "policies": [{"condition": {"value_from": "principal.market_code"}}],
        }
    )
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = _build_ctx(user_id=None)
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
    )

    response = await stream_chat_feedback(request, ctx, _request_with_service(svc))
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "SQL_POLICY_PRINCIPAL_REQUIRED"
    assert "principal.market_code" in payload["error"]
    assert "provider that populates principal fields" in payload["error"]
    assert "agent.sql_policy" in payload["error"]
    svc.chat.stream_chat.assert_not_called()
    event = audit_sink.events[-1]
    assert event.user_id is None
    assert event.action == "sql.policy.principal"
    assert event.resource_type == "chat"
    assert event.resource_id is None
    assert event.decision == "deny"
    assert event.reason == "SQL_POLICY_PRINCIPAL_REQUIRED"
    assert event.metadata == {
        "operation": "chat.feedback",
        "session_id": None,
        "subagent_id": "feedback",
        "datasource": None,
        "database": None,
        "error_code": "SQL_POLICY_PRINCIPAL_REQUIRED",
        "missing_principal_paths": ["market_code"],
    }

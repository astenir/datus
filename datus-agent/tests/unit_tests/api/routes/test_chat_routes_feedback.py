# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for POST /api/v1/chat/feedback endpoint."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

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
from datus.api.models.cli_models import FeedbackChatInput, StreamChatInput
from datus.api.routes.chat_routes import stream_chat_feedback
from datus.tools.sql_policy import SqlPolicyConfig
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


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

    response = await stream_chat_feedback(request, svc, _build_ctx())
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


@pytest.mark.asyncio
async def test_feedback_endpoint_denies_unauthorized_datasource_before_task_start(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = _build_svc()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = _build_ctx(
        datasource_grants={
            "finance": {"effect": "allow", "allow_sql": True},
        }
    )
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
        datasource="hr",
    )

    response = await stream_chat_feedback(request, svc, ctx)
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "DATASOURCE_ACCESS_DENIED"
    assert payload["error"] == "Datasource 'hr' is not authorized for this request."
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.asyncio
async def test_feedback_endpoint_denies_unauthorized_model_before_task_start():
    svc = _build_svc()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = _build_ctx()
    ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
        model="deepseek/deepseek-chat",
    )

    response = await stream_chat_feedback(request, svc, ctx)
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "MODEL_FORBIDDEN"
    assert "deepseek/deepseek-chat" in payload["error"]
    svc.chat.stream_chat.assert_not_called()


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

    response = await stream_chat_feedback(request, svc, _build_ctx())
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

    response = await stream_chat_feedback(request, svc, ctx)
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


@pytest.mark.asyncio
async def test_feedback_endpoint_rejects_quota_exceeded_before_task_start(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    await quota_store.put_quota(
        subject_type="user",
        subject_id="tester",
        resource="chat.feedback",
        limit=1,
        window_seconds=3600,
    )
    await quota_store.consume_quota(
        subjects=[{"subject_type": "user", "subject_id": "tester"}],
        resource="chat.feedback",
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store)
    )
    svc = _build_svc()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
    )

    response = await stream_chat_feedback(request, svc, _build_ctx())
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "QUOTA_EXCEEDED"
    svc.chat.stream_chat.assert_not_called()
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.resource_type == "chat"
    assert event.decision == "deny"
    assert event.reason == "quota exceeded"
    assert event.metadata["resource"] == "chat.feedback"

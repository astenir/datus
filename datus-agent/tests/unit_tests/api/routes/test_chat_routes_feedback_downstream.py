# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream datasource, model-policy, and quota coverage for chat feedback."""

import json
from unittest.mock import MagicMock

import pytest

from datus.api import deps
from datus.api.enterprise.defaults import InMemoryEnterpriseQuotaStore
from datus.api.models.downstream import FeedbackChatInput
from datus.api.routes.chat_routes import stream_chat_feedback
from datus_enterprise.config_projection import DatasourceGrantConfigProjector
from tests.unit_tests.api.routes.test_chat_routes_feedback import (
    CollectingAuditSink,
    _build_ctx,
    _build_svc,
    _enterprise_extensions,
    _request_with_service,
)


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

    response = await stream_chat_feedback(request, ctx, _request_with_service(svc))
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

    response = await stream_chat_feedback(request, ctx, _request_with_service(svc))
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "MODEL_FORBIDDEN"
    assert "deepseek/deepseek-chat" in payload["error"]
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.asyncio
async def test_feedback_endpoint_denies_malformed_model_under_policy():
    svc = _build_svc()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = _build_ctx()
    ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
    request = FeedbackChatInput(
        source_session_id="chat_session_abc",
        reaction_emoji="thumbsup",
        reference_msg="Here is your SQL result",
        model="gpt-4o",
    )

    response = await stream_chat_feedback(request, ctx, _request_with_service(svc))
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :])
    assert payload["error_type"] == "MODEL_FORBIDDEN"
    assert "gpt-4o" in payload["error"]
    svc.chat.stream_chat.assert_not_called()


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

    response = await stream_chat_feedback(request, _build_ctx(), _request_with_service(svc))
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

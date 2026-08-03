# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream enterprise security and ownership coverage for chat routes."""

import json
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from datus.api.enterprise.models import AccessDecision
from datus.api.models.base_models import Result
from datus.api.models.chat_models import ResumeChatInput
from datus.api.models.cli_models import ChatSessionData, ChatSessionItemInfo
from datus.api.models.downstream import FeedbackChatInput, StreamChatInput
from datus.api.routes.chat_routes import (
    _authorize_subagent_dispatch,
    delete_session,
    get_chat_history,
    list_sessions,
    resume_chat,
    stream_chat,
    stream_chat_feedback,
    submit_tool_result,
)
from datus.api.services.chat_task_manager import EventBufferExpiredError
from datus.tools.sql_policy import SqlPolicyConfig
from datus_enterprise.services.chat_request_policy import (
    authorize_chat_permission_mode,
    default_enterprise_chat_permission_mode,
)
from tests.unit_tests.api.routes.test_chat_routes import (
    CollectingAuditSink,
    _mock_ctx,
    _mock_svc,
    _mock_svc_with_nodes,
    _request_with_service,
)


def _patch_owner_extensions(monkeypatch, owner_store, *, enabled=False, session_body_store=None):
    import datus.api.deps as api_deps
    import datus.api.enterprise.deps as enterprise_deps
    from datus.api.enterprise.defaults import (
        InMemoryEnterpriseAgentStore,
        InMemoryEnterpriseQuotaStore,
        InMemoryEnterpriseRoleStore,
        InMemoryEnterpriseUserStore,
        PassthroughConfigProjector,
    )

    extensions = SimpleNamespace(
        enabled=enabled,
        session_owner_store=owner_store,
        session_body_store=session_body_store,
        config_projector=PassthroughConfigProjector(),
        user_store=InMemoryEnterpriseUserStore(),
        role_store=InMemoryEnterpriseRoleStore(),
        agent_store=InMemoryEnterpriseAgentStore(),
        quota_store=InMemoryEnterpriseQuotaStore(),
    )
    monkeypatch.setattr(api_deps, "get_enterprise_extensions", lambda: extensions)
    monkeypatch.setattr(enterprise_deps, "get_audit_sink", lambda: SimpleNamespace(write=AsyncMock()))
    return extensions


class TestChatPermissionModeAuthorization:
    def test_enterprise_omitted_mode_defaults_to_normal(self):
        request = StreamChatInput(message="hi", permission_mode=None)

        default_enterprise_chat_permission_mode(request, enterprise_enabled=True)

        assert request.permission_mode == "normal"

    def test_non_enterprise_keeps_permission_mode_unchanged(self):
        request = StreamChatInput(message="hi", permission_mode=None)

        default_enterprise_chat_permission_mode(request, enterprise_enabled=False)

        assert request.permission_mode is None

    @pytest.mark.asyncio
    async def test_enterprise_elevated_mode_requires_user_permission(self, monkeypatch):
        request = StreamChatInput(message="hi", permission_mode="auto")
        require_permission = AsyncMock(side_effect=HTTPException(status_code=403, detail="Permission denied."))
        monkeypatch.setattr(
            "datus_enterprise.services.chat_request_policy.require_authorized_module",
            require_permission,
        )

        with pytest.raises(HTTPException) as exc_info:
            await authorize_chat_permission_mode(
                request,
                _mock_ctx(user_id="bob", permissions={"module.chat"}),
                enterprise_enabled=True,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Permission mode 'auto' requires module.chat.permission_mode."
        require_permission.assert_awaited_once_with(
            ANY,
            "module.chat.permission_mode",
        )

    @pytest.mark.asyncio
    async def test_enterprise_elevated_mode_allows_authorized_user(self, monkeypatch):
        request = StreamChatInput(message="hi", permission_mode="dangerous")
        require_permission = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "datus_enterprise.services.chat_request_policy.require_authorized_module",
            require_permission,
        )

        await authorize_chat_permission_mode(
            request,
            _mock_ctx(user_id="alice", permissions={"module.chat.permission_mode"}),
            enterprise_enabled=True,
        )

        require_permission.assert_awaited_once_with(
            ANY,
            "module.chat.permission_mode",
        )

    @pytest.mark.asyncio
    async def test_stream_allows_authorized_elevated_mode_with_legacy_agent_ceiling(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)
        agent_record = {
            "agent_id": "custom-chat",
            "node_class": "chat",
            "scoped_context": {
                "_enterprise_agent_policy": {
                    "runtime_policy": {
                        "max_permission_mode": "normal",
                        "allow_subagent_delegation": False,
                    },
                },
            },
        }
        monkeypatch.setattr(
            "datus.api.routes.chat_routes.resolve_enterprise_agent_for_dispatch",
            AsyncMock(return_value=agent_record),
        )
        require_permission = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "datus_enterprise.services.chat_request_policy.require_authorized_module",
            require_permission,
        )
        project_config = AsyncMock(side_effect=HTTPException(status_code=403, detail="DATASOURCE_FORBIDDEN"))
        monkeypatch.setattr("datus.api.routes.chat_routes.project_request_config", project_config)
        svc = _mock_svc_with_nodes()
        request = StreamChatInput(
            message="hi",
            subagent_id="custom-chat",
            permission_mode="dangerous",
        )

        response = await stream_chat(
            request,
            _mock_ctx(user_id="alice", permissions={"module.chat.permission_mode"}),
            _request_with_service(svc),
        )

        assert isinstance(response, StreamingResponse)
        require_permission.assert_awaited_once_with(ANY, "module.chat.permission_mode")
        project_config.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("enterprise_enabled", "permission_mode"),
        [(False, "dangerous"), (True, None), (True, "normal")],
    )
    async def test_permission_mode_authorization_skips_non_elevated_requests(
        self,
        monkeypatch,
        enterprise_enabled,
        permission_mode,
    ):
        request = StreamChatInput(message="hi", permission_mode=permission_mode)
        require_permission = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "datus_enterprise.services.chat_request_policy.require_authorized_module",
            require_permission,
        )

        await authorize_chat_permission_mode(
            request,
            _mock_ctx(user_id="bob", permissions={"module.chat"}),
            enterprise_enabled=enterprise_enabled,
        )

        require_permission.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_rejects_unauthorized_elevated_mode_before_config_projection(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)
        agent_record = {
            "agent_id": "custom-chat",
            "node_class": "chat",
            "scoped_context": {
                "_enterprise_agent_policy": {
                    "runtime_policy": {"max_permission_mode": "dangerous"},
                }
            },
        }
        monkeypatch.setattr(
            "datus.api.routes.chat_routes.resolve_enterprise_agent_for_dispatch",
            AsyncMock(return_value=agent_record),
        )
        require_permission = AsyncMock(side_effect=HTTPException(status_code=403, detail="Permission denied."))
        monkeypatch.setattr(
            "datus_enterprise.services.chat_request_policy.require_authorized_module",
            require_permission,
        )
        project_config = AsyncMock(side_effect=AssertionError("config projection must not run"))
        monkeypatch.setattr("datus.api.routes.chat_routes.project_request_config", project_config)
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("chat execution must not run"))
        request = StreamChatInput(
            message="hi",
            subagent_id="custom-chat",
            permission_mode="dangerous",
        )

        with pytest.raises(HTTPException) as exc_info:
            await stream_chat(
                request,
                _mock_ctx(user_id="bob", permissions={"module.chat"}),
                _request_with_service(svc),
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Permission mode 'dangerous' requires module.chat.permission_mode."
        require_permission.assert_awaited_once()
        project_config.assert_not_awaited()
        svc.chat.stream_chat.assert_not_called()


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit sink down")


class TestEnterpriseBuiltinDispatch:
    @pytest.mark.asyncio
    async def test_agent_dispatch_has_no_node_class_module_guard(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)

        await _authorize_subagent_dispatch(
            _mock_svc_with_nodes(),
            _mock_ctx(user_id="alice", permissions=set()),
            "gen_skill",
            enterprise_agent_record={"agent_id": "gen_skill", "node_class": "gen_skill"},
        )

    @pytest.mark.asyncio
    async def test_hidden_builtin_remains_available_in_local_compatibility_mode(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=False)

        await _authorize_subagent_dispatch(
            _mock_svc_with_nodes(),
            _mock_ctx(user_id="local"),
            "gen_skill",
        )


class TestEnterprisePlanModeExplore:
    @staticmethod
    def _published_builtin_overlay(agent_id, *, runtime_policy=None, tool_policy=None):
        return {
            "agent_id": agent_id,
            "node_class": agent_id,
            "status": "published",
            "acl": {"visibility": "enterprise"},
            "scoped_context": {
                "_enterprise_agent_policy": {
                    "tool_policy": tool_policy or {"mode": "inherit", "allowed": [], "denied": []},
                    "runtime_policy": runtime_policy or {"allow_subagent_delegation": False, "allowed_subagents": []},
                }
            },
        }

    @pytest.mark.asyncio
    async def test_plan_mode_injects_acl_visible_explore_into_request_policy(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        extensions = _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)
        extensions.agent_store._agents["chat"] = self._published_builtin_overlay(
            "chat",
            runtime_policy={
                "allow_subagent_delegation": True,
                "allowed_subagents": ["gen_sql"],
            },
        )
        extensions.agent_store._agents["explore"] = self._published_builtin_overlay("explore")

        async def empty_stream(*_args, **_kwargs):
            if False:
                yield

        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(return_value=empty_stream())
        request = StreamChatInput(message="plan this", plan_mode=True)

        response = await stream_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        async for _ in response.body_iterator:
            pass

        projected_config = svc.chat.stream_chat.call_args.kwargs["agent_config"]
        assert projected_config._enterprise_allowed_agent_ids >= {"chat", "explore"}
        assert projected_config._request_required_subagent_ids == {"explore"}

    @pytest.mark.asyncio
    async def test_plan_mode_returns_typed_sse_error_when_explore_is_not_acl_visible(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        extensions = _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)
        extensions.agent_store._agents["chat"] = self._published_builtin_overlay(
            "chat",
            runtime_policy={
                "allow_subagent_delegation": True,
                "allowed_subagents": ["gen_sql"],
            },
        )
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("chat execution must not start"))
        request = StreamChatInput(message="plan this", plan_mode=True)

        response = await stream_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        chunks = [chunk.decode() if isinstance(chunk, bytes) else chunk async for chunk in response.body_iterator]
        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )

        assert payload["error_type"] == "PLAN_MODE_EXPLORE_FORBIDDEN"
        assert "Explore Agent" in payload["error"]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_plan_mode_preserves_explicit_parent_task_deny(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        extensions = _patch_owner_extensions(monkeypatch, InMemorySessionOwnerStore(), enabled=True)
        extensions.agent_store._agents["chat"] = self._published_builtin_overlay(
            "chat",
            runtime_policy={"allow_subagent_delegation": False, "allowed_subagents": []},
            tool_policy={"mode": "inherit", "allowed": [], "denied": ["sub_agent_tools.task"]},
        )
        extensions.agent_store._agents["explore"] = self._published_builtin_overlay("explore")
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("chat execution must not start"))
        request = StreamChatInput(message="plan this", plan_mode=True)

        response = await stream_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        chunks = [chunk.decode() if isinstance(chunk, bytes) else chunk async for chunk in response.body_iterator]
        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )

        assert payload["error_type"] == "PLAN_MODE_DELEGATION_FORBIDDEN"
        assert "sub_agent_tools.task" in payload["error"]
        svc.chat.stream_chat.assert_not_called()


class TestResumeChatBufferExpiry:
    @pytest.mark.asyncio
    async def test_expired_cursor_yields_typed_sse_error(self):
        async def expired_events(*_args, **_kwargs):
            raise EventBufferExpiredError("Requested event cursor 1 expired; earliest available cursor is 3.")
            yield  # pragma: no cover - keeps this function an async generator

        svc = MagicMock()
        svc.task_manager.get_task.return_value = object()
        svc.task_manager.consume_events = expired_events
        request = ResumeChatInput(session_id="s1", from_event_id=1)

        with patch(
            "datus.api.routes.chat_routes.authorize_session_access",
            new=AsyncMock(return_value=SimpleNamespace(error=None)),
        ):
            response = await resume_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))

        chunks = [chunk async for chunk in response.body_iterator]
        body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)
        payload = json.loads(next(line[6:] for line in body.splitlines() if line.startswith("data: ")))

        assert response.media_type == "text/event-stream"
        assert payload["error_type"] == "CHAT_EVENT_BUFFER_EXPIRED"
        assert payload["session_id"] == "s1"


class TestStreamChatSessionOwner:
    """Owner checks for client-supplied stream session ids."""

    @pytest.mark.asyncio
    async def test_owner_store_failure_returns_sse_error_without_starting_stream(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        class FailingOwnerStore(InMemorySessionOwnerStore):
            async def get_owner(self, project_id, session_id):
                raise RuntimeError("owner store down")

        owner_store = FailingOwnerStore()
        audit_sink = CollectingAuditSink()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=object())
        monkeypatch.setattr(
            "datus.api.enterprise.deps.get_audit_sink",
            lambda: audit_sink,
        )
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        request = StreamChatInput(message="hi", session_id="s1")

        response = await stream_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        assert "SESSION_FORBIDDEN" in chunks[0]
        svc.chat.stream_chat.assert_not_called()
        assert audit_sink.events[-1].reason == "session owner store unavailable"

    @pytest.mark.asyncio
    async def test_existing_session_id_owned_by_other_user_returns_sse_error(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.session_exists_async = AsyncMock(return_value=False)
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        request = StreamChatInput(message="hi", session_id="s1")

        response = await stream_chat(request, _mock_ctx(user_id="bob"), _request_with_service(svc))
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "SESSION_FORBIDDEN"
        assert await owner_store.get_owner("project-1", "s1") == "alice"
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_session_id_owned_by_current_user_allows_stream(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        async def empty_stream(*_args, **_kwargs):
            if False:
                yield

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.stream_chat = MagicMock(return_value=empty_stream())
        request = StreamChatInput(message="hi", session_id="s1")

        response = await stream_chat(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        async for _ in response.body_iterator:
            pass

        svc.chat.stream_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_permission_does_not_allow_cross_user_stream(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        monkeypatch.setattr(
            "datus.api.enterprise.deps.authorize",
            AsyncMock(return_value=AccessDecision(allowed=True, reason="admin session permission")),
        )
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        request = StreamChatInput(message="hi", session_id="s1")

        response = await stream_chat(
            request,
            _mock_ctx(user_id="bob", permissions={"module.admin.sessions"}),
            _request_with_service(svc),
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        assert "SESSION_FORBIDDEN" in chunks[0]
        svc.chat.stream_chat.assert_not_called()


class TestFeedbackSessionOwner:
    """Owner checks for feedback source_session_id."""

    @pytest.mark.asyncio
    async def test_feedback_source_owned_by_other_user_returns_sse_error(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "source-s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        request = FeedbackChatInput(
            source_session_id="source-s1",
            reaction_emoji="thumbsup",
            reference_msg="good answer",
        )

        response = await stream_chat_feedback(request, _mock_ctx(user_id="bob"), _request_with_service(svc))
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        assert "SESSION_FORBIDDEN" in chunks[0]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_feedback_source_owned_by_current_user_allows_stream(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        async def empty_stream(*_args, **_kwargs):
            if False:
                yield

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "source-s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        svc = _mock_svc_with_nodes()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.stream_chat = MagicMock(return_value=empty_stream())
        request = FeedbackChatInput(
            source_session_id="source-s1",
            reaction_emoji="thumbsup",
            reference_msg="good answer",
        )

        response = await stream_chat_feedback(request, _mock_ctx(user_id="alice"), _request_with_service(svc))
        async for _ in response.body_iterator:
            pass

        svc.chat.stream_chat.assert_called_once()


class TestStreamChatModelPolicy:
    """Enterprise model policy must stop unauthorized model selection before task start."""

    @pytest.mark.asyncio
    async def test_requested_model_denied_returns_sse_error(self):
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        ctx = _mock_ctx(user_id="alice")
        ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
        request = StreamChatInput(message="hi", model="claude/claude-sonnet-4-5")

        response = await stream_chat(request, ctx, _request_with_service(svc))

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        assert len(chunks) == 1
        assert "event: error" in chunks[0]
        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "MODEL_FORBIDDEN"
        assert "claude/claude-sonnet-4-5" in payload["error"]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_requested_model_denial_returns_sse_error_when_audit_sink_fails(self, monkeypatch):
        import datus.api.enterprise.deps as enterprise_deps

        monkeypatch.setattr(enterprise_deps, "get_audit_sink", lambda: FailingAuditSink())
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        ctx = _mock_ctx(user_id="alice")
        ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
        request = StreamChatInput(message="hi", model="claude/claude-sonnet-4-5")

        response = await stream_chat(request, ctx, _request_with_service(svc))

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "MODEL_FORBIDDEN"
        assert "claude/claude-sonnet-4-5" in payload["error"]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_model_denied_returns_sse_error(self):
        svc = _mock_svc_with_nodes()
        svc.agent_config._target_provider = "openai"
        svc.agent_config._target_model = "gpt-4o"
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        ctx = _mock_ctx(user_id="alice")
        ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
        request = StreamChatInput(message="hi")

        response = await stream_chat(request, ctx, _request_with_service(svc))

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "MODEL_FORBIDDEN"
        assert "openai/gpt-4o" in payload["error"]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_requested_model_denied_under_policy(self):
        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        ctx = _mock_ctx(user_id="alice")
        ctx.principal = {"model_policy": {"allowed_models": ["openai/gpt-4.1"]}}
        request = StreamChatInput(message="hi", model="gpt-4o")

        response = await stream_chat(request, ctx, _request_with_service(svc))

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "MODEL_FORBIDDEN"
        assert "gpt-4o" in payload["error"]
        svc.chat.stream_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowed_model_reaches_service(self):
        async def empty_stream(*_args, **_kwargs):
            if False:
                yield

        svc = _mock_svc_with_nodes()
        svc.chat.stream_chat = MagicMock(return_value=empty_stream())
        ctx = _mock_ctx(user_id="alice")
        ctx.principal = {"model_policy": {"allowed_model_patterns": ["openai/gpt-4*"]}}
        request = StreamChatInput(message="hi", model="openai/gpt-4.1")

        response = await stream_chat(request, ctx, _request_with_service(svc))
        async for _ in response.body_iterator:
            pass

        svc.chat.stream_chat.assert_called_once()


class TestSessionOwnerAccess:
    """Owner checks for chat session runtime endpoints."""

    @pytest.mark.asyncio
    async def test_insert_denies_non_owner_without_admin_permission(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore
        from datus.api.routes.chat_routes import insert_message

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        monkeypatch.setattr(
            "datus.api.enterprise.deps.authorize",
            AsyncMock(return_value=AccessDecision(allowed=False, reason="missing admin permission")),
        )
        task = TestInsertMessageEndpoint._make_task_with_queue()
        task.owner_user_id = "alice"
        task.accepting_inserts = True
        svc = _mock_svc(task=task)
        svc.project_id = "project-1"
        svc.chat.session_exists_async = AsyncMock(return_value=False)

        result = await insert_message(
            TestInsertMessageEndpoint._make_request("hello"),
            _mock_ctx(user_id="bob"),
            _request_with_service(svc),
        )

        assert result.success is False
        assert result.errorCode == "SESSION_FORBIDDEN"
        assert task.pending_input_queue.snapshot() == []

    @pytest.mark.asyncio
    async def test_insert_allows_admin_session_permission_for_non_owner(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore
        from datus.api.routes.chat_routes import insert_message

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "s1", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        monkeypatch.setattr(
            "datus.api.enterprise.deps.authorize",
            AsyncMock(return_value=AccessDecision(allowed=True, reason="admin session permission")),
        )
        task = TestInsertMessageEndpoint._make_task_with_queue()
        task.owner_user_id = "alice"
        task.accepting_inserts = True
        svc = _mock_svc(task=task)
        svc.project_id = "project-1"

        result = await insert_message(
            TestInsertMessageEndpoint._make_request("hello"),
            _mock_ctx(user_id="bob", permissions={"module.admin.sessions"}),
            _request_with_service(svc),
        )

        assert result.success is True
        assert task.pending_input_queue.snapshot() == ["hello"]


class TestSubmitToolResultEndpoint:
    @staticmethod
    def _make_request(session_id: str = "s1"):
        from datus.api.models.chat_models import ToolResultInput

        return ToolResultInput(session_id=session_id, call_tool_id="tc_1", tool_result={"success": 1, "result": {}})

    @staticmethod
    def _make_task_with_channel(channel):
        task = MagicMock()
        task.node.tool_channel = channel
        return task

    @pytest.mark.asyncio
    async def test_publish_success_returns_received(self):
        channel = SimpleNamespace(publish=AsyncMock())
        task = self._make_task_with_channel(channel)
        svc = _mock_svc(task=task)

        result = await submit_tool_result(self._make_request(), _mock_ctx(), _request_with_service(svc))

        assert result.success is True
        assert result.data.call_tool_id == "tc_1"
        assert result.data.status == "received"
        channel.publish.assert_awaited_once_with("tc_1", {"success": 1, "error": None, "result": {}})

    @pytest.mark.asyncio
    async def test_publish_failure_returns_stable_error(self):
        channel = SimpleNamespace(publish=AsyncMock(side_effect=RuntimeError("channel closed")))
        task = self._make_task_with_channel(channel)
        svc = _mock_svc(task=task)

        result = await submit_tool_result(self._make_request(), _mock_ctx(), _request_with_service(svc))

        assert result.success is False
        assert result.errorCode == "TOOL_RESULT_DELIVERY_FAILED"
        assert result.errorMessage == "Tool result delivery failed."
        channel.publish.assert_awaited_once()


class TestInsertMessageEndpoint:
    @staticmethod
    def _make_request(message: str = "describe customers", session_id: str = "s1"):
        from datus.api.models.chat_models import InsertMessageInput

        return InsertMessageInput(session_id=session_id, message=message)

    @staticmethod
    def _make_task_with_queue(queue=None, status="running"):
        from datus.cli.execution_state import PendingInputQueue

        task = MagicMock()
        task.status = status
        task.pending_input_queue = queue if queue is not None else PendingInputQueue()
        return task


class TestStreamChatSqlPolicyPreCheck:
    @pytest.mark.asyncio
    async def test_sql_policy_denial_returns_sse_error_when_audit_sink_fails(self, monkeypatch):
        import datus.api.enterprise.deps as enterprise_deps

        monkeypatch.setattr(enterprise_deps, "get_audit_sink", lambda: FailingAuditSink())
        svc = _mock_svc_with_nodes()
        svc.agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "x:Y",
                "policies": [{"condition": {"value_from": "principal.market_code"}}],
            }
        )
        svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
        ctx = MagicMock(user_id="alice")
        ctx.principal = {}
        request = StreamChatInput(message="hi")

        response = await stream_chat(request, ctx, _request_with_service(svc))

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

        payload = json.loads(
            next(line for line in chunks[0].splitlines() if line.startswith("data: "))[len("data: ") :]
        )
        assert payload["error_type"] == "SQL_POLICY_PRINCIPAL_REQUIRED"
        assert "principal.market_code" in payload["error"]
        svc.chat.stream_chat.assert_not_called()


class TestListSessions:
    @pytest.mark.asyncio
    async def test_pg_body_store_list_filters_orphan_sessions_without_owner_index(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "owned", "alice")
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=object())
        svc = MagicMock()
        svc.project_id = "project-1"
        ctx = _mock_ctx(user_id="alice")
        svc.chat.list_sessions_async = AsyncMock(
            return_value=Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=[
                        ChatSessionItemInfo(
                            session_id="owned",
                            created_at="2026-01-01T00:00:00Z",
                            last_updated="2026-01-01T00:00:00Z",
                        ),
                        ChatSessionItemInfo(
                            session_id="orphan",
                            created_at="2026-01-01T00:00:00Z",
                            last_updated="2026-01-01T00:00:00Z",
                        ),
                    ],
                    total_count=2,
                ),
            )
        )

        result = await list_sessions(svc, ctx, subagent_id=None)

        assert result.success is True
        assert [item.session_id for item in result.data.sessions] == ["owned"]
        assert result.data.total_count == 1


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_admin_delete_uses_target_owner_scope(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "session123", "alice")
        _patch_owner_extensions(monkeypatch, owner_store)
        monkeypatch.setattr(
            "datus.api.enterprise.deps.authorize",
            AsyncMock(return_value=AccessDecision(allowed=True, reason="admin session permission")),
        )
        svc = MagicMock()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        expected = Result[ChatSessionData](success=True, data=ChatSessionData(sessions=[], total_count=0))
        svc.chat.delete_session_async = AsyncMock(return_value=expected)

        result = await delete_session(
            "session123",
            svc,
            _mock_ctx(user_id="bob", permissions={"module.admin.sessions"}),
        )

        assert result.success is True
        svc.chat.delete_session_async.assert_awaited_once_with("session123", user_id="alice")

    @pytest.mark.asyncio
    async def test_pg_body_store_delete_denies_when_owner_index_missing(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=object())
        svc = MagicMock()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.session_exists_async = AsyncMock(return_value=True)

        result = await delete_session("orphan", svc, _mock_ctx(user_id="alice"))

        assert result.success is False
        assert result.errorCode == "RESOURCE_NOT_FOUND"
        svc.chat.delete_session_async.assert_not_called()
        assert await owner_store.get_owner("project-1", "orphan") is None


class TestGetChatHistory:
    @pytest.mark.asyncio
    async def test_pg_body_store_history_parses_raw_message_rows(self, monkeypatch, real_agent_config):
        """GET history must aggregate PG body rows before serializing SSE history."""
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore
        from datus.api.services.chat_service import ChatService

        class BodyStore:
            async def get_session_messages(self, **kwargs):
                assert kwargs == {"project_id": "project-1", "scope": "alice", "session_id": "chat_session_pg"}
                return [
                    {
                        "message_data": json.dumps({"role": "user", "content": "What is the answer?"}),
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    {
                        "message_data": json.dumps(
                            {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": json.dumps({"output": "The answer is 42."}),
                                    }
                                ],
                            }
                        ),
                        "created_at": "2026-01-01T00:00:01Z",
                    },
                ]

        owner_store = InMemorySessionOwnerStore()
        await owner_store.set_owner("project-1", "chat_session_pg", "alice")
        body_store = BodyStore()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=body_store)

        task_manager = MagicMock()
        task_manager.get_task.return_value = None
        svc = SimpleNamespace(
            project_id="project-1",
            task_manager=task_manager,
            chat=ChatService(
                agent_config=real_agent_config,
                task_manager=task_manager,
                project_id="project-1",
                session_body_store=body_store,
            ),
        )

        result = await get_chat_history(svc, _mock_ctx(user_id="alice"), session_id="chat_session_pg")

        assert result.success is True
        assert result.data.messages
        user_messages = [msg for msg in result.data.messages if msg.role == "user"]
        assistant_messages = [msg for msg in result.data.messages if msg.role == "assistant"]
        assert user_messages[0].content[0].payload["content"] == "What is the answer?"
        assert any(
            content.payload.get("content") == "The answer is 42."
            for msg in assistant_messages
            for content in msg.content
        )

    @pytest.mark.asyncio
    async def test_pg_body_store_history_denies_when_owner_index_missing(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        owner_store = InMemorySessionOwnerStore()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=object())
        svc = MagicMock()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.session_exists_async = AsyncMock(return_value=True)

        result = await get_chat_history(svc, _mock_ctx(user_id="alice"), session_id="orphan")

        assert result.success is False
        assert result.errorCode == "RESOURCE_NOT_FOUND"
        svc.chat.get_history_async.assert_not_called()
        assert await owner_store.get_owner("project-1", "orphan") is None

    @pytest.mark.asyncio
    async def test_pg_body_store_history_denies_when_owner_index_unavailable(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        class FailingOwnerStore(InMemorySessionOwnerStore):
            async def get_owner(self, project_id, session_id):
                raise RuntimeError("owner store down")

        owner_store = FailingOwnerStore()
        audit_sink = CollectingAuditSink()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True, session_body_store=object())
        monkeypatch.setattr(
            "datus.api.enterprise.deps.get_audit_sink",
            lambda: audit_sink,
        )
        svc = MagicMock()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.session_exists_async = AsyncMock(return_value=True)

        result = await get_chat_history(svc, _mock_ctx(user_id="alice"), session_id="orphan")

        assert result.success is False
        assert result.errorCode == "RESOURCE_NOT_FOUND"
        svc.chat.get_history_async.assert_not_called()
        assert audit_sink.events[-1].reason == "session owner store unavailable"

    @pytest.mark.asyncio
    async def test_history_denies_when_owner_index_backfill_fails(self, monkeypatch):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore

        class SetFailingOwnerStore(InMemorySessionOwnerStore):
            async def set_owner(self, project_id, session_id, user_id):
                raise RuntimeError("owner store down")

        owner_store = SetFailingOwnerStore()
        audit_sink = CollectingAuditSink()
        _patch_owner_extensions(monkeypatch, owner_store, enabled=True)
        monkeypatch.setattr(
            "datus.api.enterprise.deps.get_audit_sink",
            lambda: audit_sink,
        )
        svc = MagicMock()
        svc.project_id = "project-1"
        svc.task_manager.get_task.return_value = None
        svc.chat.session_exists_async = AsyncMock(return_value=True)

        result = await get_chat_history(svc, _mock_ctx(user_id="alice"), session_id="legacy")

        assert result.success is False
        assert result.errorCode == "RESOURCE_NOT_FOUND"
        svc.chat.get_history_async.assert_not_called()
        assert audit_sink.events[-1].reason == "session owner store unavailable"

"""Tests for process-local chat admission and bounded SSE retention."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from datus.api.models.cli_models import SSEErrorData, SSEEvent, SSEPingData, SSESessionData
from datus.api.services.chat_admission import (
    ChatAdmissionController,
    ChatAdmissionLimits,
    ChatCapacityError,
)
from datus.api.services.chat_task_manager import (
    ChatBufferLimits,
    ChatTask,
    ChatTaskManager,
    EventBufferExpiredError,
    EventBufferOverflowError,
)


class TestChatAdmissionController:
    @pytest.mark.asyncio
    async def test_per_user_limit_rejects_and_release_restores_capacity(self):
        controller = ChatAdmissionController(
            ChatAdmissionLimits(global_limit=10, per_project_limit=10, per_user_limit=1)
        )
        token = await controller.acquire(project_id="p1", user_id="alice")

        with pytest.raises(ChatCapacityError, match="user:alice"):
            await controller.acquire(project_id="p1", user_id="alice")

        await controller.release(token)
        replacement = await controller.acquire(project_id="p1", user_id="alice")
        await controller.release(replacement)

    @pytest.mark.asyncio
    async def test_limits_are_shared_across_projects(self):
        controller = ChatAdmissionController(ChatAdmissionLimits(global_limit=1, per_project_limit=1, per_user_limit=1))
        token = await controller.acquire(project_id="p1", user_id="alice")

        with pytest.raises(ChatCapacityError, match="worker"):
            await controller.acquire(project_id="p2", user_id="bob")

        await controller.release(token)

    @pytest.mark.asyncio
    async def test_release_is_idempotent(self):
        controller = ChatAdmissionController(ChatAdmissionLimits(global_limit=1, per_project_limit=1, per_user_limit=1))
        token = await controller.acquire(project_id="p1", user_id="alice")
        await controller.release(token)
        await controller.release(token)
        replacement = await controller.acquire(project_id="p1", user_id="alice")
        await controller.release(replacement)

    def test_limits_load_positive_api_values(self):
        limits = ChatAdmissionLimits.from_api_config(
            {"chat": {"max_active_global": "12", "max_active_per_project": 7, "max_active_per_user": 2}}
        )
        assert limits == ChatAdmissionLimits(global_limit=12, per_project_limit=7, per_user_limit=2)


class TestChatEventBufferLimits:
    @pytest.mark.asyncio
    async def test_event_count_is_trimmed_in_batches(self):
        manager = ChatTaskManager(
            buffer_limits=ChatBufferLimits(max_events=5, max_bytes=1024 * 1024, completed_ttl_seconds=60)
        )
        task = ChatTask("s1", MagicMock())

        for event_id in range(6):
            await manager._push_event(task, _ping(event_id))

        assert len(task.events) == 4
        assert task.base_offset == 2
        assert task.event_bytes == sum(task.event_sizes)

    @pytest.mark.asyncio
    async def test_resume_before_earliest_cursor_fails_explicitly(self):
        manager = ChatTaskManager()
        task = ChatTask("s1", MagicMock())
        task.base_offset = 3
        task.events = [_ping(3)]
        task.status = "completed"

        with pytest.raises(EventBufferExpiredError, match="earliest available cursor is 3"):
            await anext(manager.consume_events(task, start_from=1))

    @pytest.mark.asyncio
    async def test_trimmed_mixed_events_keep_absolute_cursor(self):
        manager = ChatTaskManager(
            buffer_limits=ChatBufferLimits(max_events=5, max_bytes=1024 * 1024, completed_ttl_seconds=60)
        )
        task = ChatTask("s1", MagicMock())
        original = [
            SSEEvent(
                id=10,
                event="session",
                data=SSESessionData(session_id="s1"),
                timestamp="2026-01-01T00:00:00Z",
            ),
            _ping(20),
            SSEEvent(
                id=40,
                event="error",
                data=SSEErrorData(error="transient", error_type="TEST", session_id="s1"),
                timestamp="2026-01-01T00:00:00Z",
            ),
            _ping(80),
            SSEEvent(
                id=160,
                event="session",
                data=SSESessionData(session_id="s1"),
                timestamp="2026-01-01T00:00:00Z",
            ),
            _ping(320),
        ]
        for event in original:
            await manager._push_event(task, event)
        task.status = "completed"

        retained = [event async for event in manager.consume_events(task, start_from=task.base_offset)]

        assert task.base_offset == 2
        assert [event.id for event in retained] == [event.id for event in original[2:]]
        assert task.consumer_offset == len(original)

    @pytest.mark.asyncio
    async def test_single_event_cannot_exceed_byte_budget(self):
        manager = ChatTaskManager(buffer_limits=ChatBufferLimits(max_events=10, max_bytes=32, completed_ttl_seconds=60))
        task = ChatTask("s1", MagicMock())

        with pytest.raises(EventBufferOverflowError, match="32-byte"):
            await manager._push_event(task, _ping(1))

        assert task.events == []

    @pytest.mark.asyncio
    async def test_completed_ttl_uses_completion_time_and_detaches_node(self):
        manager = ChatTaskManager(
            buffer_limits=ChatBufferLimits(
                max_events=10,
                max_bytes=1024,
                completed_ttl_seconds=1,
                cleanup_interval_seconds=60,
            )
        )
        task = ChatTask("s1", MagicMock())
        task.node = MagicMock()
        task.created_at = datetime.now() - timedelta(hours=1)
        task.completed_at = datetime.now()
        task.status = "completed"
        manager._tasks["s1"] = task

        manager._release_task_slot("s1", task)
        assert manager._completed_tasks["s1"] is task
        assert task.node is None

        task.completed_at = datetime.now() - timedelta(seconds=2)
        manager._purge_expired_completed()
        assert manager._completed_tasks == {}
        await manager.shutdown()


def _ping(event_id: int) -> SSEEvent:
    return SSEEvent(id=event_id, event="ping", data=SSEPingData(), timestamp="2026-01-01T00:00:00Z")

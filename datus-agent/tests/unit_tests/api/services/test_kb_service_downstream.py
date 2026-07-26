"""Downstream cancellation coverage for knowledge base bootstrap streams."""

from threading import Event
from unittest.mock import patch

import pytest

from datus.api.models.kb_downstream import BootstrapDocInput
from datus.api.services.kb_service import KbService
from datus.configuration.agent_config import DocumentConfig
from datus.schemas.batch_events import BatchEvent, BatchStage
from tests.unit_tests.api.services.test_kb_service import _bootstrap_input


@pytest.mark.asyncio
class TestKbServiceBootstrapStream:
    async def test_bootstrap_stream_reports_running_component_cancellation(self, real_agent_config):
        """A cancel signal raised during a component must stop the stream instead of reporting success."""
        import asyncio

        svc = KbService(agent_config=real_agent_config)
        cancel_event = asyncio.Event()
        worker_can_finish = Event()
        request = _bootstrap_input(components=["metadata", "reference_sql"], strategy="check")

        def fake_run_component(request, component, queue, loop, cancel_event, project_root, config):  # noqa: ARG001
            loop.call_soon_threadsafe(
                queue.put_nowait,
                BatchEvent(
                    biz_name="metadata_init",
                    stage=BatchStage.TASK_STARTED,
                    message=f"{component} started",
                ),
            )
            worker_can_finish.wait()
            return {"status": "success", "message": f"{component} completed"}

        with patch.object(svc, "_run_component", side_effect=fake_run_component):
            events = []
            async for event in svc.bootstrap_stream(
                request, "cancel-running", cancel_event, str(real_agent_config.home)
            ):
                events.append(event)
                if event.stage == BatchStage.TASK_STARTED.value:
                    cancel_event.set()
                    worker_can_finish.set()

        assert [event.component for event in events] == ["metadata", "metadata", "all"]
        assert events[1].stage == BatchStage.TASK_FAILED.value
        assert events[1].error == "Cancelled by user"
        assert events[2].message == "Bootstrap cancelled"


@pytest.mark.asyncio
class TestKbServiceBootstrapDocStream:
    async def test_bootstrap_doc_stream_reports_running_cancellation(self, real_agent_config):
        """A doc cancel signal raised during init must stop the stream instead of reporting success."""
        import asyncio

        from datus.storage.document.doc_init import InitResult

        real_agent_config.document_configs["slow_doc"] = DocumentConfig(type="local", source="/nonexistent")
        svc = KbService(agent_config=real_agent_config)
        cancel_event = asyncio.Event()
        worker_can_finish = Event()
        request = BootstrapDocInput(platform="slow_doc", build_mode="overwrite")

        def fake_run_doc_init(request, queue, loop, cancel_event):  # noqa: ARG001
            loop.call_soon_threadsafe(
                queue.put_nowait,
                BatchEvent(
                    biz_name="doc_init",
                    stage=BatchStage.TASK_STARTED,
                    message="doc init started",
                ),
            )
            worker_can_finish.wait()
            return InitResult(
                platform="slow_doc",
                version="unknown",
                source="/nonexistent",
                total_docs=1,
                total_chunks=1,
                success=True,
                errors=[],
                duration_seconds=0.05,
            )

        with patch.object(svc, "_run_doc_init", side_effect=fake_run_doc_init):
            events = []
            async for event in svc.bootstrap_doc_stream(request, "cancel-doc-running", cancel_event):
                events.append(event)
                if event.stage == BatchStage.TASK_STARTED.value:
                    cancel_event.set()
                    worker_can_finish.set()

        assert [event.stage for event in events] == [
            BatchStage.TASK_STARTED.value,
            BatchStage.TASK_FAILED.value,
        ]
        assert events[1].component == "platform_doc"
        assert events[1].error == "Cancelled by user"

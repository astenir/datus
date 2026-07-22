# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from unittest.mock import MagicMock

import pytest

from datus.cli.execution_state import ExecutionInterrupted
from datus.models.stream_interrupt import handle_stream_interrupt


class _SessionStub:
    def __init__(self, items=None):
        self.items = list(items or [])

    async def get_items(self):
        return list(self.items)


@pytest.mark.asyncio
async def test_interrupt_without_completed_task_remains_immediate():
    result = MagicMock()
    controller = MagicMock(is_interrupted=True)

    with pytest.raises(ExecutionInterrupted):
        await handle_stream_interrupt(
            interrupt_controller=controller,
            result=result,
            session=_SessionStub(),
            completed_task_call_ids=set(),
            graceful_interrupt_requested=False,
        )

    result.cancel.assert_not_called()


@pytest.mark.asyncio
async def test_interrupt_with_persisted_task_result_remains_immediate():
    result = MagicMock()
    controller = MagicMock(is_interrupted=True)
    session = _SessionStub([{"type": "function_call_output", "call_id": "task-call"}])

    with pytest.raises(ExecutionInterrupted):
        await handle_stream_interrupt(
            interrupt_controller=controller,
            result=result,
            session=session,
            completed_task_call_ids={"task-call"},
            graceful_interrupt_requested=False,
        )

    result.cancel.assert_not_called()

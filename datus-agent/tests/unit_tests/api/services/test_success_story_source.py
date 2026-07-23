# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Trusted success-story source resolution from canonical chat histories."""

from unittest.mock import AsyncMock

import pytest

from datus.api.services.chat_service import ChatService, SuccessStorySourceError
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus


def _tool_actions(
    call_id="call_sql",
    tool_name="execute_sql",
    sql="SELECT 1",
    *,
    success=True,
    start_datasource="ccks_fund",
    completion_datasource="ccks_fund",
):
    start_arguments = {"sql": sql}
    completion_arguments = {"sql": sql}
    if start_datasource is not None:
        start_arguments["datasource"] = start_datasource
    if completion_datasource is not None:
        completion_arguments["datasource"] = completion_datasource
    start = ActionHistory(
        action_id=call_id,
        role=ActionRole.TOOL,
        action_type=tool_name,
        input={"function_name": tool_name, "arguments": start_arguments},
        status=ActionStatus.PROCESSING,
    )
    complete = ActionHistory(
        action_id=f"complete_{call_id}",
        role=ActionRole.TOOL,
        action_type=tool_name,
        input={"function_name": tool_name, "arguments": completion_arguments},
        output={"raw_output": {"success": 1 if success else 0, "result": []}},
        status=ActionStatus.SUCCESS if success else ActionStatus.FAILED,
    )
    return start, complete


def _messages(*actions, question="show one"):
    return [
        {"role": "user", "content": question},
        {"role": "assistant", "actions": list(actions)},
    ]


@pytest.fixture
def chat_svc(real_agent_config):
    return ChatService(real_agent_config, project_id="project-1")


@pytest.mark.asyncio
async def test_resolves_successful_root_execute_sql(chat_svc):
    start, complete = _tool_actions()
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    source = await chat_svc.resolve_success_story_source_async(
        "chat_session_root",
        "call_sql",
        user_id="alice",
        session_link="/chat/chat_session_root",
    )

    assert source.question == "show one"
    assert source.sql == "SELECT 1"
    assert source.datasource_id == "ccks_fund"
    assert source.subagent_name == "chat"
    assert source.session_link == "/chat/chat_session_root"


@pytest.mark.asyncio
async def test_resolves_historical_read_query(chat_svc):
    start, complete = _tool_actions(tool_name="db_tools.read_query")
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    source = await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert source.sql == "SELECT 1"
    assert source.datasource_id == "ccks_fund"


@pytest.mark.asyncio
async def test_nested_sql_uses_root_question_and_child_agent(chat_svc):
    task_start = ActionHistory(
        action_id="call_task",
        role=ActionRole.TOOL,
        action_type="task",
        input={"function_name": "task", "arguments": {"type": "gen_sql"}},
        status=ActionStatus.PROCESSING,
    )
    start, complete = _tool_actions()
    root_messages = _messages(task_start, question="root business question")
    child_messages = _messages(start, complete, question="internal child prompt")
    chat_svc._load_success_story_history_async = AsyncMock(
        return_value=(
            root_messages,
            {"call_task": child_messages},
            {"call_task": "gen_sql_session_child"},
        )
    )

    source = await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert source.question == "root business question"
    assert source.datasource_id == "ccks_fund"
    assert source.subagent_name == "gen_sql"


@pytest.mark.asyncio
async def test_uses_completion_datasource_when_start_action_omits_it(chat_svc):
    start, complete = _tool_actions(start_datasource=None)
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    source = await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert source.datasource_id == "ccks_fund"


@pytest.mark.asyncio
async def test_equivalent_datasource_aliases_are_accepted(chat_svc):
    start, complete = _tool_actions()
    start.input["arguments"]["datasource_id"] = " ccks_fund "
    complete.input["arguments"]["datasource_name"] = "ccks_fund"
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    source = await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert source.datasource_id == "ccks_fund"


@pytest.mark.asyncio
async def test_conflicting_datasource_aliases_are_rejected(chat_svc):
    start, complete = _tool_actions()
    start.input["arguments"]["datasource_id"] = "datus_enterprise"
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    with pytest.raises(SuccessStorySourceError) as exc:
        await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert exc.value.code == "SUCCESS_STORY_DATASOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_missing_datasource_is_rejected(chat_svc):
    start, complete = _tool_actions(start_datasource=None, completion_datasource=None)
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    with pytest.raises(SuccessStorySourceError) as exc:
        await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert exc.value.code == "SUCCESS_STORY_DATASOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_conflicting_datasources_are_rejected(chat_svc):
    start, complete = _tool_actions(completion_datasource="datus_enterprise")
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    with pytest.raises(SuccessStorySourceError) as exc:
        await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert exc.value.code == "SUCCESS_STORY_DATASOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_failed_completion_is_rejected(chat_svc):
    start, complete = _tool_actions(success=False)
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(start, complete), {}, {}))

    with pytest.raises(SuccessStorySourceError) as exc:
        await chat_svc.resolve_success_story_source_async("chat_session_root", "call_sql")

    assert exc.value.code == "SUCCESS_STORY_NOT_SUCCESSFUL"


@pytest.mark.asyncio
async def test_missing_call_is_rejected(chat_svc):
    chat_svc._load_success_story_history_async = AsyncMock(return_value=(_messages(), {}, {}))

    with pytest.raises(SuccessStorySourceError) as exc:
        await chat_svc.resolve_success_story_source_async("chat_session_root", "missing")

    assert exc.value.code == "SUCCESS_STORY_SOURCE_NOT_FOUND"

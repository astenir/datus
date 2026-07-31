"""Tests for datus.api.services.action_sse_converter — ActionHistory to SSE conversion."""

import json
from datetime import datetime

from datus.api.models.cli_models import IMessageContent, SSEDataType, SSEEvent
from datus.api.services.action_sse_converter import (
    _build_error_content,
    _build_response_content,
    action_to_history_sse_event,
    action_to_sse_event,
)
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus


def _make_action(**overrides) -> ActionHistory:
    """Helper: build ActionHistory with sensible defaults."""
    defaults = {
        "action_id": "act-001",
        "role": ActionRole.ASSISTANT,
        "action_type": "test_action",
        "status": ActionStatus.SUCCESS,
        "messages": "",
        "input": None,
        "output": None,
        "start_time": datetime(2025, 1, 1, 12, 0, 0),
        "end_time": datetime(2025, 1, 1, 12, 0, 5),
    }
    defaults.update(overrides)
    return ActionHistory(**defaults)


def _assert_content_list(contents):
    assert isinstance(contents, list)
    assert isinstance(contents[0], IMessageContent)
    return contents


def _assert_sse_event(event):
    assert isinstance(event, SSEEvent)
    return event


class TestBuildResponseContentDownstream:
    """Tests for _build_response_content."""

    def test_response_unwraps_json_output_envelope(self):
        """Persisted model output envelopes render their user-facing text."""
        action = _make_action(output={"raw_output": '{"output": "The answer is 42."}'})
        contents = _build_response_content(action)
        assert len(contents) == 1
        assert contents[0].type == "markdown"
        assert contents[0].payload["content"] == "The answer is 42."


class TestBuildErrorContentDownstream:
    """Tests for _build_error_content."""

    def test_preserves_structured_error_type(self):
        """Structured error type is available to real-time SSE consumers."""
        action = _make_action(output={"error": "Permission denied", "error_type": "PERMISSION_DENIED"})
        contents = _build_error_content(action)
        assert contents[0].payload == {"content": "Permission denied", "error_type": "PERMISSION_DENIED"}


class TestActionToHistorySseEvent:
    """Tests for persisted-history-only action conversion."""

    def test_plan_preview_remains_visible_markdown_in_history(self):
        action = _make_action(
            role=ActionRole.ASSISTANT,
            status=ActionStatus.SUCCESS,
            action_type="plan_preview",
            messages="\n---\n\n# Plan\n\n- Inspect metadata",
            output={
                "content": "\n---\n\n# Plan\n\n- Inspect metadata",
                "content_type": "markdown",
            },
        )

        event = action_to_history_sse_event(action, event_id=1, message_id="plan-preview-1")

        event = _assert_sse_event(event)
        content = event.data.payload.content[0]
        assert content.type == "plan-preview"
        assert content.payload == {"content": "\n---\n\n# Plan\n\n- Inspect metadata"}

    def test_ask_user_result_becomes_read_only_summary(self):
        action = _make_action(
            role=ActionRole.TOOL,
            status=ActionStatus.SUCCESS,
            action_type="ask_user",
            input={
                "function_name": "ask_user",
                "arguments": json.dumps(
                    {
                        "questions": [
                            {
                                "title": "County",
                                "question": "Which county?",
                                "options": ["Los Angeles", "San Francisco"],
                                "multi_select": False,
                            }
                        ]
                    }
                ),
            },
            output={"success": 1, "result": json.dumps([{"question": "Which county?", "answer": "Los Angeles"}])},
        )
        event = action_to_history_sse_event(action, event_id=1, message_id="msg-1")
        event = _assert_sse_event(event)
        content = event.data.payload.content[0]
        assert content.type == "interaction-summary"
        assert "interactionKey" not in content.payload
        assert content.payload["status"] == "answered"
        assert content.payload["requests"][0]["content"] == "Which county?"
        assert content.payload["requests"][0]["options"] == [
            {"key": "1", "title": "Los Angeles"},
            {"key": "2", "title": "San Francisco"},
        ]
        assert content.payload["answers"] == [{"question": "Which county?", "answer": "Los Angeles"}]

    def test_history_does_not_replay_live_interaction_control(self):
        action = _make_action(
            role=ActionRole.INTERACTION,
            status=ActionStatus.PROCESSING,
            action_type="request_choice",
            input={"events": [{"content": "Choose"}]},
        )
        assert action_to_history_sse_event(action, event_id=1, message_id="msg-1") is None

    def test_tool_result_does_not_infer_duration_from_message_timestamps(self):
        action = _make_action(
            action_id="complete_tool-call-1",
            role=ActionRole.TOOL,
            status=ActionStatus.SUCCESS,
            action_type="list_tables",
            input={"function_name": "list_tables", "arguments": {}},
            output={"success": 1, "result": ["orders"]},
        )

        event = _assert_sse_event(action_to_history_sse_event(action, event_id=1, message_id="msg-1"))

        content = event.data.payload.content[0]
        assert content.type == "call-tool-result"
        assert "duration" not in content.payload

    def test_cancelled_ask_user_result_is_read_only_summary(self):
        action = _make_action(
            role=ActionRole.TOOL,
            status=ActionStatus.SUCCESS,
            action_type="ask_user",
            input={"function_name": "ask_user", "arguments": {"questions": [{"question": "Continue?"}]}},
            output={"success": 0, "error": "User cancelled the question"},
        )
        event = _assert_sse_event(action_to_history_sse_event(action, event_id=1, message_id="msg-1"))
        content = event.data.payload.content[0]
        assert content.type == "interaction-summary"
        assert content.payload["status"] == "cancelled"
        assert content.payload["error"] == "User cancelled the question"


class TestActionToSSEEventDownstream:
    """Tests for the main action_to_sse_event dispatcher."""

    def test_plan_preview_renders_as_markdown_in_live_stream(self):
        action = _make_action(
            role=ActionRole.ASSISTANT,
            status=ActionStatus.SUCCESS,
            action_type="plan_preview",
            messages="\n---\n\n# Plan\n\n- Inspect metadata",
            output={
                "content": "\n---\n\n# Plan\n\n- Inspect metadata",
                "content_type": "markdown",
            },
        )

        event = action_to_sse_event(action, event_id=21, message_id="plan-preview-1")

        event = _assert_sse_event(event)
        content = event.data.payload.content[0]
        assert content.type == "plan-preview"
        assert content.payload == {"content": "\n---\n\n# Plan\n\n- Inspect metadata"}

    def test_response_delta_uses_markdown_content(self):
        """Normal assistant response chunks stream as markdown, not reasoning."""
        action = _make_action(
            role=ActionRole.ASSISTANT,
            status=ActionStatus.PROCESSING,
            action_type="response_delta",
            output={"delta": "Normal answer"},
        )
        event = action_to_sse_event(
            action, event_id=22, message_id="response-22", stream_thinking=True, is_first_delta=True
        )
        event = _assert_sse_event(event)
        assert event.data.type == SSEDataType.CREATE_MESSAGE
        assert event.data.payload.content[0].type == "markdown"
        assert event.data.payload.content[0].payload["content"] == "Normal answer"

    def test_markdown_content_type_overrides_internal_phase_flag(self):
        """Pre-tool assistant text remains markdown even when it is not the final turn response."""
        action = _make_action(
            role=ActionRole.ASSISTANT,
            status=ActionStatus.SUCCESS,
            action_type="response",
            output={"raw_output": "I will inspect the schema.", "is_thinking": True, "content_type": "markdown"},
        )
        event = action_to_sse_event(action, event_id=23, message_id="response-23")
        event = _assert_sse_event(event)
        assert event.data.payload.content[0].type == "markdown"

"""History-only ActionHistory to SSE conversion helpers."""

import json
from typing import Any, List, Optional

from datus.api.models.cli_models import (
    IMessageContent,
    SSEDataType,
    SSEEvent,
    SSEMessageData,
    SSEMessagePayload,
)
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.utils.time_utils import now_utc_iso, to_utc_iso


def _parse_json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _extract_interaction_questions(action: ActionHistory) -> List[dict[str, Any]]:
    """Extract ask_user questions from a persisted tool-call action."""
    from datus.api.services.action_sse_converter import _extract_function

    _, arguments = _extract_function(action)
    questions = _parse_json_value(arguments.get("questions", []))
    if not isinstance(questions, list):
        return []

    requests: List[dict[str, Any]] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue

        content = str(question.get("question") or question.get("content") or "").strip()
        if not content:
            continue

        options_payload = None
        raw_options = question.get("options")
        raw_choices = question.get("choices")
        if isinstance(raw_options, list) and raw_options:
            options_payload = [{"key": str(i), "title": str(option)} for i, option in enumerate(raw_options, 1)]
        elif isinstance(raw_choices, dict) and raw_choices:
            options_payload = [{"key": str(key), "title": str(title)} for key, title in raw_choices.items()]

        payload: dict[str, Any] = {
            "title": str(question.get("title") or f"Question {index + 1}"),
            "content": content,
            "contentType": str(question.get("content_type") or question.get("contentType") or "markdown"),
            "allowFreeText": bool(question.get("allow_free_text", question.get("allowFreeText", True))),
            "multiSelect": bool(question.get("multi_select", question.get("multiSelect", False))),
        }
        default_choice = question.get("default_choice", question.get("defaultChoice"))
        if default_choice is not None:
            payload["defaultChoice"] = str(default_choice)
        if options_payload:
            payload["options"] = options_payload
        requests.append(payload)

    return requests


def _coerce_tool_success(value: Any) -> Optional[bool]:
    if value in (1, True, "1", "true", "True", "success", "SUCCESS"):
        return True
    if value in (0, False, "0", "false", "False", "failed", "FAILED"):
        return False
    return None


def _extract_interaction_result(action: ActionHistory) -> tuple[str, list[dict[str, Any]], Optional[str]]:
    """Extract answer summary from ask_user's FuncToolResult-style output."""
    from datus.api.services.action_sse_converter import _extract_error, _is_tool_result_envelope

    raw_output = action.output.get("raw_output", action.output) if isinstance(action.output, dict) else action.output
    raw_output = _parse_json_value(raw_output)

    success = action.status != ActionStatus.FAILED
    error = _extract_error(raw_output)
    result_value = raw_output

    if _is_tool_result_envelope(raw_output):
        coerced_success = _coerce_tool_success(raw_output.get("success"))
        if coerced_success is not None:
            success = coerced_success
        if "result" in raw_output:
            result_value = raw_output.get("result")
        error = error or _extract_error(raw_output)

    if action.status == ActionStatus.FAILED:
        success = False
        error = error or action.messages or "Unknown error"

    result_value = _parse_json_value(result_value)
    answers: list[dict[str, Any]] = []
    if isinstance(result_value, list):
        for item in result_value:
            if not isinstance(item, dict):
                continue
            payload: dict[str, Any] = {"answer": item.get("answer")}
            if item.get("question"):
                payload["question"] = str(item.get("question"))
            answers.append(payload)
    elif result_value not in (None, "") and success:
        answers.append({"answer": result_value})

    status = "answered" if success else "failed"
    if error and "cancel" in error.lower():
        status = "cancelled"
    return status, answers, error


def _build_interaction_summary_content(action: ActionHistory) -> List[IMessageContent]:
    """Build a read-only history block for completed ask_user interactions."""
    status, answers, error = _extract_interaction_result(action)
    payload: dict[str, Any] = {
        "status": status,
        "actionType": action.action_type,
        "requests": _extract_interaction_questions(action),
    }
    if answers:
        payload["answers"] = answers
    if error:
        payload["error"] = error
    return [IMessageContent(type="interaction-summary", payload=payload)]


def action_to_history_sse_event(
    action: ActionHistory,
    event_id: int,
    message_id: str,
    include_user_message: bool = False,
    include_final_response: bool = False,
) -> Optional[SSEEvent]:
    """Convert an action for persisted chat history without replaying live controls."""
    from datus.api.services.action_sse_converter import action_to_sse_event

    if action.role == ActionRole.TOOL and action.action_type == "ask_user":
        if action.status == ActionStatus.PROCESSING:
            return None
        contents = _build_interaction_summary_content(action)
        return SSEEvent(
            id=event_id,
            event="message",
            data=SSEMessageData(
                type=SSEDataType.CREATE_MESSAGE,
                payload=SSEMessagePayload(
                    message_id=message_id,
                    role="assistant",
                    content=contents,
                    depth=action.depth,
                    parent_action_id=action.parent_action_id,
                ),
            ),
            timestamp=to_utc_iso(getattr(action, "start_time", None)) or now_utc_iso(),
        )

    if action.role == ActionRole.INTERACTION:
        return None

    return action_to_sse_event(
        action,
        event_id,
        message_id,
        include_user_message=include_user_message,
        include_final_response=include_final_response,
    )

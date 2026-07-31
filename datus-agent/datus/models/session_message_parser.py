# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Shared parser for persisted SDK session message rows."""

import ast
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.schemas.tool_summary import detect_tool_failure
from datus.utils.loggings import get_logger
from datus.utils.message_utils import extract_user_input
from datus.utils.time_utils import to_utc_iso

logger = get_logger(__name__)

ParseFinalOutput = Callable[[List[ActionHistory], Dict[str, Any]], Optional[ActionHistory]]
RestoreNativeToolCall = Callable[[Dict[str, Any], List[ActionHistory], List[str], Optional[str]], None]
AttachNativeToolResult = Callable[[List[ActionHistory], Optional[str], Any, Optional[str]], None]


def message_rows_to_raw_messages(
    message_rows: List[Any],
    *,
    parse_final_output: ParseFinalOutput,
    restore_native_tool_call: RestoreNativeToolCall,
    attach_native_tool_result: AttachNativeToolResult,
) -> List[Dict[str, Any]]:
    """Convert persisted SDK message rows into API-ready raw chat messages."""
    messages = []
    current_assistant_group = None
    assistant_progress = []
    current_actions = []

    for row in message_rows:
        if isinstance(row, dict):
            message_data = row.get("message_data")
            created_at = row.get("created_at")
        else:
            message_data, created_at = row

        created_at_iso = to_utc_iso(created_at)
        try:
            message_json = json.loads(message_data)
            role = message_json.get("role", "")
            msg_type = message_json.get("type", "")

            if role == "user":
                raw_user_content = message_json.get("content", "")
                if isinstance(raw_user_content, list):
                    tool_results = [
                        block
                        for block in raw_user_content
                        if isinstance(block, dict) and block.get("type") == "tool_result"
                    ]
                    has_user_text = any(
                        isinstance(block, dict) and block.get("type") in ("text", "input_text", "output_text")
                        for block in raw_user_content
                    )
                    if tool_results and not has_user_text:
                        for tool_result in tool_results:
                            attach_native_tool_result(
                                current_actions,
                                tool_result.get("tool_use_id"),
                                tool_result.get("content"),
                                str(created_at) if created_at else None,
                            )
                        continue

                if current_assistant_group:
                    final_action = parse_final_output(current_actions, current_assistant_group)
                    if final_action:
                        current_actions.append(final_action)

                    if current_actions:
                        current_assistant_group["actions"] = current_actions.copy()
                    if assistant_progress:
                        current_assistant_group["progress_messages"] = assistant_progress.copy()

                    messages.append(current_assistant_group)
                    current_assistant_group = None
                    assistant_progress = []
                    current_actions = []

                content = extract_user_input(message_json.get("content", ""))
                messages.append(
                    {
                        "role": "user",
                        "content": content,
                        "timestamp": created_at_iso,
                        "created_at": created_at_iso,
                    }
                )
                continue

            if msg_type == "reasoning":
                summary = message_json.get("summary", [])
                if isinstance(summary, str):
                    summary_texts = [summary]
                elif isinstance(summary, list):
                    summary_texts = [
                        str(item.get("text", "")).strip()
                        for item in summary
                        if isinstance(item, dict) and str(item.get("text", "")).strip()
                    ]
                else:
                    summary_texts = []
                reasoning_text = "\n\n".join(summary_texts).strip()
                if reasoning_text:
                    if not current_assistant_group:
                        current_assistant_group = {
                            "role": "assistant",
                            "content": "",
                            "timestamp": created_at_iso,
                            "created_at": created_at_iso,
                        }
                    assistant_progress.append(f"💭Thinking: {reasoning_text}")
                    provider_data = message_json.get("provider_data")
                    provider_data = provider_data if isinstance(provider_data, dict) else {}
                    response_id = (
                        provider_data.get("response_id")
                        or message_json.get("id")
                        or f"assistant_{uuid.uuid5(uuid.NAMESPACE_URL, f'{created_at}|{message_data}').hex}"
                    )
                    current_actions.append(
                        ActionHistory(
                            action_id=f"{response_id}:reasoning",
                            role=ActionRole.ASSISTANT,
                            messages=reasoning_text,
                            action_type="thinking",
                            input=None,
                            output={"thinking": reasoning_text},
                            status=ActionStatus.SUCCESS,
                            start_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                            end_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                        )
                    )
                continue

            if msg_type == "function_call":
                tool_name = message_json.get("name", "unknown")
                arguments = message_json.get("arguments", "{}")

                if not current_assistant_group:
                    current_assistant_group = {
                        "role": "assistant",
                        "content": "",
                        "timestamp": created_at_iso,
                        "created_at": created_at_iso,
                    }

                try:
                    args_dict = json.loads(arguments) if arguments else {}
                    args_str = str(args_dict)[:60]
                    assistant_progress.append(f"✓ Tool call: {tool_name}({args_str})")
                except (json.JSONDecodeError, ValueError, TypeError):
                    assistant_progress.append(f"✓ Tool call: {tool_name}")

                action = ActionHistory(
                    action_id=message_json.get("call_id", str(uuid.uuid4())),
                    role=ActionRole.TOOL,
                    messages=f"Tool call: {tool_name}",
                    action_type=tool_name,
                    input={"function_name": tool_name, "arguments": arguments},
                    output=None,
                    status=ActionStatus.PROCESSING,
                    start_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                )
                current_actions.append(action)
                continue

            if msg_type == "function_call_output":
                if current_actions:
                    output_call_id = message_json.get("call_id")
                    last_action = None
                    if output_call_id:
                        for candidate in reversed(current_actions):
                            if candidate.action_id == output_call_id and candidate.status == ActionStatus.PROCESSING:
                                last_action = candidate
                                break
                    if last_action is None:
                        last_action = current_actions[-1]

                    output_text = message_json.get("output", "")
                    output_data = {}
                    if output_text:
                        try:
                            output_data = ast.literal_eval(output_text)
                        except (ValueError, SyntaxError):
                            try:
                                output_data = json.loads(output_text)
                            except json.JSONDecodeError:
                                output_data = {"result": output_text}

                    call_id = message_json.get("call_id", last_action.action_id)
                    failed = detect_tool_failure(output_data)
                    success_action = ActionHistory(
                        action_id="complete_" + call_id,
                        role=ActionRole.TOOL,
                        messages=f"Tool result: {last_action.action_type}",
                        action_type=last_action.action_type,
                        input=last_action.input,
                        output=output_data,
                        status=ActionStatus.FAILED if failed else ActionStatus.SUCCESS,
                        start_time=last_action.start_time,
                        end_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                    )
                    current_actions.append(success_action)
                continue

            if role == "assistant":
                content_array = message_json.get("content", [])
                provider_data = message_json.get("provider_data")
                provider_data = provider_data if isinstance(provider_data, dict) else {}
                response_id = (
                    provider_data.get("response_id")
                    or message_json.get("id")
                    or f"assistant_{uuid.uuid5(uuid.NAMESPACE_URL, f'{created_at}|{message_data}').hex}"
                )

                for item in content_array:
                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("type", "")
                    text = item.get("text", "")

                    if item_type == "thinking":
                        thinking_text = str(item.get("thinking", "") or "").strip()
                        if thinking_text:
                            if not current_assistant_group:
                                current_assistant_group = {
                                    "role": "assistant",
                                    "content": "",
                                    "timestamp": created_at_iso,
                                    "created_at": created_at_iso,
                                }
                            assistant_progress.append(f"💭Thinking: {thinking_text}")
                            current_actions.append(
                                ActionHistory(
                                    action_id=f"{response_id}:reasoning",
                                    role=ActionRole.ASSISTANT,
                                    messages=thinking_text,
                                    action_type="thinking",
                                    input=None,
                                    output={"thinking": thinking_text, "content_type": "thinking"},
                                    status=ActionStatus.SUCCESS,
                                    start_time=(
                                        datetime.fromisoformat(str(created_at)) if created_at else datetime.now()
                                    ),
                                    end_time=(
                                        datetime.fromisoformat(str(created_at)) if created_at else datetime.now()
                                    ),
                                )
                            )

                    if item_type in ("output_text", "text") and text:
                        if not current_assistant_group:
                            current_assistant_group = {
                                "role": "assistant",
                                "content": "",
                                "timestamp": created_at_iso,
                                "created_at": created_at_iso,
                            }

                        assistant_progress.append(text)
                        response_action = ActionHistory(
                            action_id=f"{response_id}:response",
                            role=ActionRole.ASSISTANT,
                            messages=text,
                            action_type="response",
                            input=None,
                            output={"raw_output": text, "is_thinking": False, "content_type": "markdown"},
                            status=ActionStatus.SUCCESS,
                            start_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                            end_time=datetime.fromisoformat(str(created_at)) if created_at else datetime.now(),
                        )
                        current_actions.append(response_action)

                    if item_type in ("tool_use", "server_tool_use"):
                        if not current_assistant_group:
                            current_assistant_group = {
                                "role": "assistant",
                                "content": "",
                                "timestamp": created_at_iso,
                                "created_at": created_at_iso,
                            }
                        restore_native_tool_call(
                            item,
                            current_actions,
                            assistant_progress,
                            str(created_at) if created_at else None,
                        )

                    if item_type in ("web_search_tool_result", "web_fetch_tool_result"):
                        attach_native_tool_result(
                            current_actions,
                            item.get("tool_use_id"),
                            item.get("content"),
                            str(created_at) if created_at else None,
                        )

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.debug(f"Skipping malformed message: {exc}")
            continue

    if current_assistant_group:
        final_action = parse_final_output(current_actions, current_assistant_group)
        if final_action:
            current_actions.append(final_action)

        if not current_assistant_group.get("content"):
            current_assistant_group["content"] = "Processing completed"
        if assistant_progress:
            current_assistant_group["progress_messages"] = assistant_progress
        if current_actions:
            current_assistant_group["actions"] = current_actions.copy()
        messages.append(current_assistant_group)

    return messages

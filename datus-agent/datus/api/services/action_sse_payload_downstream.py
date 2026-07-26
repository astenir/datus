"""Downstream payload normalization for ActionHistory SSE messages."""

from typing import Any

from datus.utils.json_utils import llm_result2json


def normalize_response_parts(action_output: Any) -> tuple[Any, Any]:
    output = action_output if isinstance(action_output, dict) else {}
    response = output.get("response") or output.get("content") or output.get("raw_output") or ""
    parsed_response = llm_result2json(response) if isinstance(response, str) else None
    if not isinstance(parsed_response, dict):
        return output.get("sql"), response

    sql = output.get("sql") or parsed_response.get("sql")
    response = (
        parsed_response.get("response")
        or parsed_response.get("output")
        or parsed_response.get("explanation")
        or response
    )
    return sql, response


def error_payload(output: Any, error_message: Any) -> dict[str, Any]:
    payload = {"content": error_message}
    error_type = output.get("error_type") if isinstance(output, dict) else None
    if error_type:
        payload["error_type"] = str(error_type)
    return payload

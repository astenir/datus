"""Pure record normalization helpers for PostgreSQL session bodies."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from datus.utils.time_utils import to_utc_iso


async def _ensure_body(conn: Any, project_id: str, scope: str, session_id: str) -> None:
    await conn.execute(
        """
        INSERT INTO enterprise_session_bodies (project_id, scope, session_id, created_at, updated_at)
        VALUES ($1, $2, $3, now(), now())
        ON CONFLICT(project_id, scope, session_id) DO UPDATE SET updated_at=now()
        """,
        project_id,
        scope,
        session_id,
    )


def _normalize_project_id(project_id: str | None) -> str:
    value = str(project_id or "").strip()
    return value or "default"


def _normalize_scope(scope: str | None) -> str:
    return str(scope or "")


def _loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    return to_utc_iso(value)


def _is_user_message(item: Any) -> bool:
    return isinstance(item, dict) and item.get("role") == "user"


def _classify_message_type(item: Any) -> str:
    if isinstance(item, dict):
        if item.get("role") == "user":
            return "user"
        if item.get("role") == "assistant":
            return "assistant"
        if item.get("type"):
            return str(item.get("type"))
    return "other"


def _extract_tool_name(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if item_type in {"mcp_call", "mcp_approval_request"} and "server_label" in item:
        server_label = item.get("server_label")
        tool_name = item.get("name")
        if tool_name and server_label:
            return f"{server_label}.{tool_name}"
        if server_label:
            return str(server_label)
        if tool_name:
            return str(tool_name)
    if item_type in {"computer_call", "file_search_call", "web_search_call", "code_interpreter_call"}:
        return str(item_type)
    if "name" in item:
        name = item.get("name")
        return str(name) if name is not None else None
    return None


def _details_json(value: Any) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, dict):
            return json.dumps(value)
        return json.dumps(value.__dict__)
    except (TypeError, ValueError):
        return None


def _usage_record(row: Any, *, include_turn: bool) -> dict[str, Any]:
    if row is None:
        return {}
    record = {
        "requests": int(row["requests"] or 0),
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "input_tokens_details": _loads(row["input_tokens_details"]) if row["input_tokens_details"] else None,
        "output_tokens_details": _loads(row["output_tokens_details"]) if row["output_tokens_details"] else None,
    }
    if include_turn:
        record = {"user_turn_number": int(row["user_turn_number"] or 0), **record}
    return record

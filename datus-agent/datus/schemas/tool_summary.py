# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unified per-tool one-line summary helpers.

The registry provides result-based summaries for SSE/API and CLI consumers.
The live/history display contract goes through :func:`summarize_tool_execution`,
which keeps failures result-based while preferring the submitted statement for
SQL execution tools.

Only the ``success`` path is per-tool; failure summaries are produced uniformly
by :func:`format_failure`. Input summaries use an explicit safe-field allow-list
and are bounded separately from the compact result registry.

All non-filesystem result summaries are clipped to ``SUMMARY_TEXT_MAX_CHARS``
characters at the result-registry exit; filesystem tools (``read_file``,
``write_file``, ``edit_file``, ``glob``, ``grep``) bypass that result clip.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


SUMMARY_TEXT_MAX_CHARS = 19
SUMMARY_ERROR_MAX_CHARS = 19
INPUT_SUMMARY_MAX_CHARS = 240
SQL_INPUT_SUMMARY_TOOLS = frozenset(
    {"execute_sql", "read_query", "query", "execute_write", "execute_ddl", "write_query"}
)

# Filesystem tools want full path/count visibility; web tools want their
# result titles / page label visible on the compact line rather than clipped
# to a handful of characters.
FS_TOOLS_NO_CLIP = frozenset(
    {"read_file", "write_file", "edit_file", "delete_file", "glob", "grep", "web_search", "web_fetch"}
)
HYBRID_INPUT_RESULT_TOOLS = frozenset(
    {
        "analyze_column_usage_patterns",
        "analyze_metric_candidates_from_history",
        "analyze_table_relationships",
        "ask_user",
        "attribution_analyze",
        "check_semantic_model_exists",
        "check_semantic_object_exists",
        "end_metric_generation",
        "end_semantic_model_generation",
        "parse_temporal_expressions",
        "profile_semantic_model_evidence",
        "validate_semantic",
        "validate_skill",
    }
)


# ── Generic helpers (public API) ────────────────────────────────────────


def pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def truncate_text(text: str, limit: int = SUMMARY_TEXT_MAX_CHARS) -> str:
    first_line = next((line for line in text.splitlines() if line.strip()), "").strip()
    if not first_line:
        return "Empty result"
    if len(first_line) <= limit:
        return first_line
    return first_line[: limit - 1].rstrip() + "…"


def _clean_input_text(value: Any, *, limit: int = INPUT_SUMMARY_MAX_CHARS) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _arg_text(arguments: dict, *keys: str, limit: int = INPUT_SUMMARY_MAX_CHARS) -> str:
    for key in keys:
        text = _clean_input_text(arguments.get(key), limit=limit)
        if text:
            return text
    return ""


def _arg_list(arguments: dict, *keys: str) -> list[str]:
    for key in keys:
        value = arguments.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            if stripped.startswith("["):
                try:
                    value = json.loads(stripped)
                except (TypeError, ValueError):
                    return [stripped]
            else:
                return [stripped]
        if isinstance(value, (list, tuple)):
            items = [_clean_input_text(item, limit=80) for item in value]
            return [item for item in items if item]
    return []


def _list_preview(items: list[str], *, limit: int = 3) -> str:
    if not items:
        return ""
    visible = items[:limit]
    preview = "、".join(visible)
    if len(items) > limit:
        preview = f"{preview} +{len(items) - limit}"
    return preview


def _join_summary(*parts: str, separator: str = " · ") -> str:
    return separator.join(part for part in parts if part)


def _namespace_summary(arguments: dict, *, include_schema: bool = True) -> str:
    namespace = [
        _arg_text(arguments, "catalog"),
        _arg_text(arguments, "database", "database_name", "databaseName"),
    ]
    if include_schema:
        namespace.append(_arg_text(arguments, "schema_name", "schemaName", "schema"))
    qualified = ".".join(part for part in namespace if part)
    datasource = _arg_text(arguments, "datasource", "datasource_id", "datasourceId")
    return _join_summary(datasource, qualified)


def _qualified_table_summary(arguments: dict) -> str:
    table = _arg_text(arguments, "table_name", "table", "name")
    namespace = _namespace_summary(arguments)
    if namespace and table:
        if " · " in namespace:
            datasource, qualified = namespace.split(" · ", 1)
            return _join_summary(datasource, f"{qualified}.{table}")
        return f"{namespace}.{table}"
    return table or namespace


def _query_with_scope_summary(arguments: dict) -> str:
    query = _arg_text(arguments, "query_text", "query", "keywords", "search_text", "description")
    return _join_summary(query, _namespace_summary(arguments))


def _fields_summary(*keys: str) -> Callable[[dict], str]:
    def formatter(arguments: dict) -> str:
        return _join_summary(*(_arg_text(arguments, key) for key in keys))

    return formatter


def _first_field_summary(*keys: str) -> Callable[[dict], str]:
    return lambda arguments: _arg_text(arguments, *keys)


def _sql_input_summary(arguments: dict) -> str:
    # SQL is intentionally not clipped here. The UI applies its own visual
    # limit while the expanded card retains the exact submitted statement.
    return _arg_text(arguments, "sql", "query", "statement", limit=10**9)


def _transfer_input_summary(arguments: dict) -> str:
    source = _arg_text(arguments, "source_datasource")
    target = _arg_text(arguments, "target_table")
    target_datasource = _arg_text(arguments, "target_datasource")
    route = " → ".join(part for part in (source, _join_summary(target_datasource, target, separator=".")) if part)
    return route or _arg_text(arguments, "source_sql", limit=10**9)


def _metrics_query_input_summary(arguments: dict) -> str:
    metrics = _list_preview(_arg_list(arguments, "metrics"))
    dimensions = _list_preview(_arg_list(arguments, "dimensions"))
    date_range = "～".join(
        part for part in (_arg_text(arguments, "time_start"), _arg_text(arguments, "time_end")) if part
    )
    return _join_summary(metrics, dimensions, date_range)


def _attribution_input_summary(arguments: dict) -> str:
    baseline = "～".join(
        part for part in (_arg_text(arguments, "baseline_start"), _arg_text(arguments, "baseline_end")) if part
    )
    current = "～".join(
        part for part in (_arg_text(arguments, "current_start"), _arg_text(arguments, "current_end")) if part
    )
    comparison = " → ".join(part for part in (baseline, current) if part)
    return _join_summary(_arg_text(arguments, "metric_name"), comparison)


def _reference_template_input_summary(arguments: dict) -> str:
    subject = _list_preview(_arg_list(arguments, "subject_path"))
    name = _arg_text(arguments, "name", "template_id")
    params = arguments.get("params")
    param_count = f"{len(params)} params" if isinstance(params, dict) and params else ""
    datasource = _arg_text(arguments, "datasource")
    return _join_summary(subject, name, param_count, datasource)


def _file_search_input_summary(arguments: dict) -> str:
    pattern = _arg_text(arguments, "pattern")
    path = _arg_text(arguments, "path")
    include = _arg_text(arguments, "include")
    return _join_summary(pattern, path, include)


def _todo_write_input_summary(arguments: dict) -> str:
    todos = arguments.get("todos_json")
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except (TypeError, ValueError):
            return ""
    if not isinstance(todos, list) or not todos:
        return ""
    first = todos[0] if isinstance(todos[0], dict) else {}
    title = _arg_text(first, "title", "content", "description")
    count = f"{len(todos)} todos"
    return _join_summary(count, title)


def _task_input_summary(arguments: dict) -> str:
    return _join_summary(
        _arg_text(arguments, "type", "subagent_type", "subagentType"),
        _arg_text(arguments, "prompt", "description"),
    )


def _question_input_summary(arguments: dict) -> str:
    questions = arguments.get("questions")
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except (TypeError, ValueError):
            return ""
    if not isinstance(questions, list) or not questions:
        return ""
    first = questions[0]
    if not isinstance(first, dict):
        return ""
    question = _arg_text(first, "question", "title")
    return f"{question} +{len(questions) - 1}" if question and len(questions) > 1 else question


def _generation_files_input_summary(arguments: dict) -> str:
    files = _arg_list(arguments, "semantic_model_files")
    if not files:
        single = _arg_text(arguments, "metric_file", "semantic_model_file")
        files = [single] if single else []
    return _list_preview(files)


def _discovery_input_summary(arguments: dict) -> str:
    tables = _list_preview(_arg_list(arguments, "tables"))
    table = _arg_text(arguments, "table_name")
    query = _arg_text(arguments, "query_text")
    return _join_summary(query or tables or table, _namespace_summary(arguments))


def _safe_url_input_summary(arguments: dict) -> str:
    raw = _arg_text(arguments, "url")
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if not parsed.netloc:
        path = parsed.path
        if "@" in path:
            path = path.rsplit("@", 1)[-1]
        return path
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        host = f"{host}:{port}"
    return f"{host}{parsed.path or '/'}"


def _memory_add_input_summary(arguments: dict) -> str:
    content = _arg_text(arguments, "content", limit=10**9)
    return f"add memory · {len(content)} chars" if content else ""


def _memory_edit_input_summary(arguments: dict) -> str:
    old = _arg_text(arguments, "old_string", limit=10**9)
    new = _arg_text(arguments, "new_string", limit=10**9)
    if not old and not new:
        return ""
    return f"edit memory · {len(old)}→{len(new)} chars"


def _osi_metrics_input_summary(arguments: dict) -> str:
    path = _arg_text(arguments, "path")
    metrics = arguments.get("metrics_json")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, ValueError):
            metrics = None
    if isinstance(metrics, list):
        return _join_summary(path, f"{len(metrics)} metrics")
    if isinstance(metrics, dict):
        nested = metrics.get("metrics")
        count = len(nested) if isinstance(nested, list) else len(metrics)
        return _join_summary(path, f"{count} metrics")
    return path


InputFormatterFn = Callable[[dict], str]


class ToolInputSummaryRegistry:
    """Explicit allow-list for safe, stable summaries derived from tool input."""

    def __init__(self) -> None:
        self._formatters: Dict[str, InputFormatterFn] = {}

    def register(self, tool_name: str, fn: InputFormatterFn) -> None:
        self._formatters[tool_name] = fn

    def names(self) -> list[str]:
        return sorted(self._formatters)

    def summarize(self, arguments: Any, tool_name: str) -> str:
        parsed = arguments
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except (TypeError, ValueError):
                return ""
        if not isinstance(parsed, dict):
            return ""
        formatter = self._formatters.get(tool_name)
        if formatter is None:
            return ""
        try:
            summary = formatter(parsed).strip()
            if tool_name in SQL_INPUT_SUMMARY_TOOLS:
                return summary
            return _clean_input_text(summary)
        except Exception as fmt_err:  # pragma: no cover - defensive
            logger.debug(f"Tool input summary formatter for {tool_name} raised: {fmt_err}")
            return ""


def _register_input_summaries(registry: ToolInputSummaryRegistry) -> None:
    formatters: Dict[str, InputFormatterFn] = {
        # Database tools and compatibility names.
        "execute_sql": _sql_input_summary,
        "read_query": _sql_input_summary,
        "query": _sql_input_summary,
        "execute_write": _sql_input_summary,
        "execute_ddl": _sql_input_summary,
        "write_query": _sql_input_summary,
        "describe_table": _qualified_table_summary,
        "list_tables": _namespace_summary,
        "table_overview": _namespace_summary,
        "list_databases": lambda args: _join_summary(
            _arg_text(args, "datasource", "datasource_id", "datasourceId"),
            _arg_text(args, "catalog"),
        ),
        "list_schemas": lambda args: _namespace_summary(args, include_schema=False),
        "search_table": _query_with_scope_summary,
        "transfer_query_result": _transfer_input_summary,
        # BI tools.
        "list_dashboards": _first_field_summary("search"),
        "get_dashboard": _first_field_summary("dashboard_id"),
        "list_charts": _first_field_summary("dashboard_id"),
        "get_chart": _fields_summary("dashboard_id", "chart_id"),
        "get_chart_data": _fields_summary("dashboard_id", "chart_id"),
        "list_datasets": _first_field_summary("dashboard_id"),
        "create_dashboard": _first_field_summary("title", "name"),
        "update_dashboard": _fields_summary("dashboard_id", "title"),
        "delete_dashboard": _first_field_summary("dashboard_id"),
        "create_chart": _fields_summary("title", "chart_type"),
        "update_chart": _fields_summary("chart_id", "title", "chart_type"),
        "add_chart_to_dashboard": lambda args: " → ".join(
            part for part in (_arg_text(args, "chart_id"), _arg_text(args, "dashboard_id")) if part
        ),
        "delete_chart": _first_field_summary("chart_id"),
        "create_dataset": _fields_summary("name", "database_id"),
        "delete_dataset": _first_field_summary("dataset_id"),
        # Semantic query, validation, and discovery tools.
        "list_metrics": _first_field_summary("path"),
        "get_dimensions": _fields_summary("metric_name", "path"),
        "query_metrics": _metrics_query_input_summary,
        "validate_semantic": lambda args: _join_summary(
            _arg_text(args, "scope"), _list_preview(_arg_list(args, "checks"))
        ),
        "attribution_analyze": _attribution_input_summary,
        "search_metrics": lambda args: _join_summary(
            _arg_text(args, "query_text", "query"), _list_preview(_arg_list(args, "subject_path"))
        ),
        "search_reference_sql": lambda args: _join_summary(
            _arg_text(args, "query_text", "query"), _list_preview(_arg_list(args, "subject_path"))
        ),
        "search_semantic_objects": lambda args: _join_summary(
            _arg_text(args, "query_text", "query"), _list_preview(_arg_list(args, "kinds"))
        ),
        "check_semantic_object_exists": _fields_summary("kind", "name", "table_context", "object_name"),
        "check_semantic_model_exists": lambda args: _join_summary(
            _namespace_summary(
                {
                    **args,
                    "catalog": args.get("catalog_name", args.get("catalog")),
                    "database": args.get("database_name", args.get("database")),
                    "schema_name": args.get("schema_name", args.get("schema")),
                }
            ),
            _arg_text(args, "table_name"),
        ),
        "end_semantic_model_generation": _generation_files_input_summary,
        "end_metric_generation": _generation_files_input_summary,
        "analyze_table_relationships": _discovery_input_summary,
        "analyze_column_usage_patterns": _discovery_input_summary,
        "profile_semantic_model_evidence": _discovery_input_summary,
        "analyze_metric_candidates_from_history": _discovery_input_summary,
        "get_multiple_tables_ddl": _discovery_input_summary,
        # Scheduler tools.
        "submit_sql_job": _fields_summary("job_name", "sql_file_path", "conn_id"),
        "submit_sparksql_job": _fields_summary("job_name", "sql_file_path", "spark_master"),
        "trigger_scheduler_job": _first_field_summary("job_id"),
        "get_scheduler_job": _first_field_summary("job_id"),
        "pause_job": _first_field_summary("job_id"),
        "resume_job": _first_field_summary("job_id"),
        "delete_job": _first_field_summary("job_id"),
        "delete_scheduler_job": _first_field_summary("job_id"),
        "update_job": _fields_summary("job_id", "job_name", "sql_file_path"),
        "list_job_runs": _first_field_summary("job_id"),
        "get_run_log": _fields_summary("job_id", "run_id"),
        # Subject context and reference templates.
        "get_metrics": lambda args: _join_summary(
            _list_preview(_arg_list(args, "subject_path")), _arg_text(args, "name", "metric_name", "metric_id")
        ),
        "get_reference_sql": lambda args: _join_summary(
            _list_preview(_arg_list(args, "subject_path")), _arg_text(args, "name", "ref_id", "sql_id")
        ),
        "search_reference_template": lambda args: _join_summary(
            _arg_text(args, "query_text", "query"), _list_preview(_arg_list(args, "subject_path"))
        ),
        "get_reference_template": _reference_template_input_summary,
        "render_reference_template": _reference_template_input_summary,
        "execute_reference_template": _reference_template_input_summary,
        # Filesystem tools. Content and replacement text are deliberately not
        # included in compact summaries.
        "read_file": _first_field_summary("path", "file_path"),
        "write_file": _first_field_summary("path", "file_path"),
        "edit_file": _first_field_summary("path", "file_path"),
        "delete_file": _first_field_summary("path", "file_path"),
        "glob": _file_search_input_summary,
        "grep": _file_search_input_summary,
        # Todo, date, skill, interaction, and sub-agent tools.
        "todo_read": _first_field_summary("todo_id"),
        "todo_write": _todo_write_input_summary,
        "todo_update": _fields_summary("todo_id", "status"),
        "parse_temporal_expressions": _first_field_summary("task_text", "expression", "text", "query"),
        "search_skill_usage": _first_field_summary("skill_name"),
        "load_skill": _first_field_summary("skill_name", "name"),
        "validate_skill": _first_field_summary("skill_path"),
        "ask_user": _question_input_summary,
        "task": _task_input_summary,
        # Platform documentation and web tools.
        "list_document_nav": _fields_summary("platform", "version"),
        "get_document": lambda args: _join_summary(
            _arg_text(args, "platform"), _list_preview(_arg_list(args, "titles")), _arg_text(args, "version")
        ),
        "search_document": lambda args: _join_summary(
            _arg_text(args, "platform"), _list_preview(_arg_list(args, "keywords")), _arg_text(args, "version")
        ),
        "web_search": lambda args: _list_preview(_arg_list(args, "keywords", "query", "query_text")),
        "web_fetch": _safe_url_input_summary,
        # Active built-ins that do not yet have result-summary formatters.
        "bash": _first_field_summary("command"),
        "get_dataset": _fields_summary("dashboard_id", "dataset_id"),
        "start_new_report": _fields_summary("slug", "name"),
        "bind_existing_report": _first_field_summary("report_slug"),
        "save_query": _fields_summary("name", "goal"),
        "start_new_dashboard": _fields_summary("slug", "name"),
        "bind_existing_dashboard": _first_field_summary("dashboard_slug"),
        "save_query_template": _fields_summary("name", "goal"),
        "create_issue_comment": _first_field_summary("issue_id"),
        "update_issue_status": _fields_summary("issue_id", "status"),
        "request_human_input": _fields_summary("issue_id", "question"),
        "mark_blocked": _fields_summary("issue_id", "reason"),
        "finish_mission": _fields_summary("issue_id", "outcome", "summary"),
        "upsert_osi_metrics": _osi_metrics_input_summary,
        "add_memory": _memory_add_input_summary,
        "edit_memory": _memory_edit_input_summary,
    }
    for name, formatter in formatters.items():
        registry.register(name, formatter)


TOOL_INPUT_SUMMARY_REGISTRY = ToolInputSummaryRegistry()
_register_input_summaries(TOOL_INPUT_SUMMARY_REGISTRY)


def looks_like_failure(data: dict) -> bool:
    success = data.get("success")
    if success is False or success == 0:
        return True
    error = data.get("error")
    if isinstance(error, str) and error.strip():
        return True
    return False


def detect_tool_failure(output_content: Any) -> bool:
    """Return True when a tool's output payload signals failure.

    Tools built on :class:`~datus.tools.func_tool.base.FuncToolResult` report
    errors via ``success=0`` / non-empty ``error`` instead of raising, so the
    model integrations cannot infer failure from "did the call throw". Every
    backend (OpenAI-compatible, Claude-native, Codex) must run the returned
    payload through this helper to render ✗ and mark the action FAILED.

    Accepts the raw ``ToolCallOutputItem.output`` shape: a dict (normal SDK
    path), a JSON string, or anything else (treated as non-failure).
    """
    data: Optional[dict] = None
    if isinstance(output_content, dict):
        data = output_content
    elif isinstance(output_content, str):
        try:
            parsed = json.loads(output_content)
        except (TypeError, ValueError):
            return False
        if isinstance(parsed, dict):
            data = parsed
    if data is None:
        return False
    return looks_like_failure(data)


def summarize_tool_execution(output_content: Any, tool_name: str, arguments: Any = None) -> str:
    """Build the display summary shared by live tool events and history replay.

    Failures always take priority. Successful tools use an explicit allow-list
    of safe input fields when the invocation target is more useful than a
    result count. Validation and analysis tools keep the target first and append
    their compact result. Missing/unknown inputs fall back to result summaries.
    """
    normalized_name = str(tool_name or "").strip().lower().rsplit(".", 1)[-1]
    if detect_tool_failure(output_content):
        return _summarize_tool_output(output_content, normalized_name)

    input_summary = TOOL_INPUT_SUMMARY_REGISTRY.summarize(arguments, normalized_name)
    if input_summary and normalized_name in HYBRID_INPUT_RESULT_TOOLS:
        result_summary = _summarize_tool_output(output_content, normalized_name)
        if result_summary not in ("", "OK", "Empty result") and result_summary != input_summary:
            return _join_summary(input_summary, result_summary)
        return input_summary
    if input_summary:
        return input_summary

    return _summarize_tool_output(output_content, normalized_name)


def summarize_tool_input(tool_name: str, arguments: Any = None) -> str:
    """Build the stable running-state summary for a tool invocation."""
    normalized_name = str(tool_name or "").strip().lower().rsplit(".", 1)[-1]
    return TOOL_INPUT_SUMMARY_REGISTRY.summarize(arguments, normalized_name)


def _summarize_tool_output(output_content: Any, tool_name: str) -> str:
    if isinstance(output_content, str):
        return TOOL_SUMMARY_REGISTRY.summarize_content(output_content, tool_name)
    return TOOL_SUMMARY_REGISTRY.summarize_dict(output_content, tool_name)


def format_failure(data: dict) -> str:
    error = data.get("error")
    if not isinstance(error, str) or not error.strip():
        return "Failed"
    return f"Failed: {truncate_text(error, SUMMARY_ERROR_MAX_CHARS)}"


def is_empty_result(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, str)) and len(value) == 0:
        return True
    return False


def format_list_envelope(value: dict) -> str:
    """Default rendering for a ``FuncToolListResult`` payload."""
    return _envelope_with_label(value, "item", "items")


def format_generic_result(value: Any) -> str:
    """Tool-agnostic fallback when a per-tool formatter is missing or returns ``""``."""
    if isinstance(value, dict):
        if "items" in value and isinstance(value["items"], list):
            return format_list_envelope(value)
        for key in ("row_count", "affected_rows", "rows_affected"):
            if isinstance(value.get(key), int):
                return pluralize(value[key], "row")
        if isinstance(value.get("count"), int):
            return pluralize(value["count"], "item")
        if isinstance(value.get("rows"), int):
            return pluralize(value["rows"], "row")
        return "OK"
    if isinstance(value, list):
        return pluralize(len(value), "item")
    if isinstance(value, bool):
        return "OK" if value else "Failed"
    if isinstance(value, int):
        return pluralize(value, "row")
    if isinstance(value, str):
        return truncate_text(value)
    return "OK"


# ── Per-tool helpers ────────────────────────────────────────────────────


def _envelope_with_label(value: Any, singular: str, plural: str) -> str:
    """Render a ``FuncToolListResult`` payload with a tool-specific noun.

    Compact format: ``"N noun"`` / ``"N/total noun"`` / ``"... noun+"``
    when ``has_more`` is set.
    """
    if not isinstance(value, dict) or "items" not in value:
        return ""
    items = value.get("items") or []
    n = len(items)
    noun = singular if n == 1 else plural
    total = value.get("total")
    if isinstance(total, int) and total != n:
        base = f"{n}/{total} {noun}"
    else:
        base = f"{n} {noun}"
    if value.get("has_more"):
        base = f"{base}+"
    return base


def _list_count(value: Any, singular: str, plural: str) -> str:
    """Render a plain ``list`` payload (no envelope)."""
    if not isinstance(value, list):
        return ""
    n = len(value)
    return f"{n} {singular}" if n == 1 else f"{n} {plural}"


def _clip_short(text: str, tool_name: str = "", limit: int = SUMMARY_TEXT_MAX_CHARS) -> str:
    """Final-stage clip applied at registry exit.

    Filesystem tools (``read_file``, ``write_file``, ``edit_file``,
    ``delete_file``, ``glob``, ``grep``) are exempt — their summaries are
    returned verbatim because users want full path / count visibility there.
    """
    if not isinstance(text, str):
        return text
    if tool_name in FS_TOOLS_NO_CLIP:
        return text
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ── Tool-specific formatters ────────────────────────────────────────────
#
# Each formatter takes the unwrapped ``result`` field of a FuncToolResult
# (success path only) and returns a one-line summary, or ``""`` to fall
# back to the generic formatter. The registry exit applies _clip_short.


# === Database tools ===


def _fmt_read_query(result: Any) -> str:
    if isinstance(result, dict):
        rows = result.get("original_rows")
        cols = result.get("column_count")
        if cols is None:
            compressed = result.get("compressed_data")
            if isinstance(compressed, str) and compressed:
                first_line = compressed.split("\n", 1)[0]
                if first_line:
                    cols = len(first_line.split(","))
        if isinstance(rows, int) and isinstance(cols, int):
            return f"{rows}×{cols} rows"
        if isinstance(rows, int):
            return pluralize(rows, "row")
    if isinstance(result, list):
        return pluralize(len(result), "row")
    return ""


def _fmt_execute_write(result: Any) -> str:
    if isinstance(result, dict):
        for key in ("row_count", "affected_rows", "rows_affected"):
            if isinstance(result.get(key), int):
                return f"+{pluralize(result[key], 'row')}"
    return ""


def _fmt_execute_ddl(result: Any) -> str:
    if isinstance(result, dict) and result.get("message"):
        return "DDL OK"
    return ""


def _fmt_execute_sql(result: Any) -> str:
    """Unified ``execute_sql`` summary — dispatches by result payload shape.

    Read results carry ``compressed_data``/``original_rows``; write results
    carry a row count; DDL results carry only a ``message``.
    """
    if isinstance(result, dict):
        if "compressed_data" in result or "original_rows" in result:
            return _fmt_read_query(result)
        # ``execute_write`` always emits a ``message`` and may legitimately
        # report ``row_count: None``, so classify a write by its ``sql_type``
        # (or any row-count key) BEFORE the DDL ``message`` check — otherwise an
        # INSERT/UPDATE/DELETE with an unknown row count would be mislabeled
        # "DDL OK".
        if result.get("sql_type") in {"insert", "update", "delete"} or any(
            key in result for key in ("row_count", "affected_rows", "rows_affected")
        ):
            return _fmt_execute_write(result) or "Write OK"
        if result.get("message"):
            return _fmt_execute_ddl(result)
    return _fmt_read_query(result)


def _fmt_describe_table(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    columns = result.get("columns") or result.get("schema")
    if isinstance(columns, list):
        n = len(columns)
        return f"{n} col" if n == 1 else f"{n} cols"
    return ""


def _fmt_list_tables(result: Any) -> str:
    if isinstance(result, list):
        return _list_count(result, "table", "tables")
    return ""


def _fmt_list_databases(result: Any) -> str:
    if isinstance(result, list):
        n = len(result)
        return f"{n} db" if n == 1 else f"{n} dbs"
    return ""


def _fmt_list_schemas(result: Any) -> str:
    if isinstance(result, list):
        return _list_count(result, "schema", "schemas")
    return ""


def search_table_result_counts(result: Any) -> tuple[int, int]:
    """Return table and sample-row counts from the current search_table result shape."""
    if not isinstance(result, dict):
        return 0, 0

    metadata = result.get("metadata")
    if not isinstance(metadata, list):
        return 0, 0

    sample_count = sum(
        len(sample_rows)
        for item in metadata
        if isinstance(item, dict) and isinstance((sample_rows := item.get("sample_rows")), list)
    )

    return len(metadata), sample_count


def _fmt_search_table(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    n, sample_rows = search_table_result_counts(result)
    if n == 0 and sample_rows == 0:
        return "no matches"
    tbl_label = "tbl" if n == 1 else "tbls"
    if sample_rows:
        return f"{n} {tbl_label}, {sample_rows} rows"
    return f"{n} {tbl_label}"


def _fmt_transfer_query_result(result: Any) -> str:
    if isinstance(result, dict):
        for key in ("row_count", "rows_transferred", "rows", "affected_rows"):
            if isinstance(result.get(key), int):
                rows = result[key]
                target = result.get("target_table")
                if target:
                    return f"moved {rows}→{target}"
                return f"moved {pluralize(rows, 'row')}"
    return ""


# === BI tools ===


def _fmt_list_dashboards(result: Any) -> str:
    return _envelope_with_label(result, "dashboard", "dashboards")


def _fmt_get_dashboard(result: Any) -> str:
    if isinstance(result, dict):
        title = result.get("title") or result.get("name")
        charts = result.get("charts")
        if title and isinstance(charts, list):
            return f"dash: {title} ({len(charts)})"
        if title:
            return f"dash: {title}"
        dash_id = result.get("dashboard_id") or result.get("id")
        if dash_id:
            return f"dash {dash_id}"
    return ""


def _fmt_list_charts(result: Any) -> str:
    return _envelope_with_label(result, "chart", "charts")


def _fmt_get_chart(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name") or result.get("title")
        if name:
            return f"chart: {name}"
        chart_id = result.get("chart_id") or result.get("id")
        if chart_id:
            return f"chart {chart_id}"
    return ""


def _fmt_get_chart_data(result: Any) -> str:
    if isinstance(result, dict):
        rows = result.get("row_count")
        if rows is None and isinstance(result.get("rows"), list):
            rows = len(result["rows"])
        cols = result.get("column_names")
        if isinstance(rows, int) and isinstance(cols, list):
            return f"{rows}r × {len(cols)}c"
        if isinstance(rows, int):
            return pluralize(rows, "row")
    return ""


def _fmt_list_datasets(result: Any) -> str:
    return _envelope_with_label(result, "dataset", "datasets")


def _fmt_create_dashboard(result: Any) -> str:
    if isinstance(result, dict):
        title = result.get("title") or result.get("name")
        dash_id = result.get("dashboard_id") or result.get("id")
        if title:
            return f"created: {title}"
        if dash_id:
            return f"created: {dash_id}"
    return ""


def _fmt_update_dashboard(result: Any) -> str:
    if isinstance(result, dict):
        title = result.get("title") or result.get("name")
        dash_id = result.get("dashboard_id") or result.get("id")
        if title:
            return f"updated: {title}"
        if dash_id:
            return f"updated: {dash_id}"
    return ""


def _fmt_delete_dashboard(result: Any) -> str:
    if isinstance(result, dict):
        title = result.get("title") or result.get("name")
        deleted = result.get("deleted")
        dash_id = result.get("dashboard_id") or result.get("id")
        if deleted is False and dash_id:
            return f"not deleted: {dash_id}"
        if title:
            return f"deleted: {title}"
        if dash_id:
            return f"deleted: {dash_id}"
        if deleted:
            return "deleted dashboard"
    return ""


def _fmt_create_chart(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name") or result.get("title")
        chart_id = result.get("chart_id") or result.get("id")
        if name:
            return f"created: {name}"
        if chart_id:
            return f"created: {chart_id}"
    return ""


def _fmt_update_chart(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name") or result.get("title")
        chart_id = result.get("chart_id") or result.get("id")
        if name:
            return f"updated: {name}"
        if chart_id:
            return f"updated: {chart_id}"
    return ""


def _fmt_add_chart_to_dashboard(result: Any) -> str:
    if isinstance(result, dict):
        chart_id = result.get("chart_id")
        dash_id = result.get("dashboard_id")
        if chart_id and dash_id:
            return f"chart {chart_id}→dash {dash_id}"
    return ""


def _fmt_delete_chart(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name") or result.get("title")
        chart_id = result.get("chart_id") or result.get("id")
        if name:
            return f"deleted: {name}"
        if chart_id:
            return f"deleted: {chart_id}"
        if result.get("deleted"):
            return "deleted chart"
    return ""


def _fmt_create_dataset(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name")
        dataset_id = result.get("dataset_id") or result.get("id")
        if name:
            return f"created: {name}"
        if dataset_id:
            return f"created: {dataset_id}"
    return ""


def _fmt_list_bi_databases(result: Any) -> str:
    if isinstance(result, list):
        n = len(result)
        return f"{n} BI db" if n == 1 else f"{n} BI dbs"
    return ""


def _fmt_delete_dataset(result: Any) -> str:
    if isinstance(result, dict):
        dataset_id = result.get("dataset_id") or result.get("id")
        if dataset_id:
            return f"deleted: {dataset_id}"
        if result.get("deleted"):
            return "deleted dataset"
    return ""


def _fmt_write_query(result: Any) -> str:
    if isinstance(result, dict):
        rows = result.get("rows_written")
        table = result.get("table_name")
        if isinstance(rows, int) and table:
            return f"+{rows}→{table}"
        if isinstance(rows, int):
            return f"+{pluralize(rows, 'row')}"
    return ""


# === Semantic tools ===


def _fmt_list_metrics(result: Any) -> str:
    return _envelope_with_label(result, "metric", "metrics")


def _fmt_get_dimensions(result: Any) -> str:
    return _envelope_with_label(result, "dimension", "dimensions")


def _fmt_query_metrics(result: Any) -> str:
    if isinstance(result, dict):
        cols = result.get("columns")
        data = result.get("data")
        rows: Optional[int] = None
        if isinstance(data, dict):
            rows = data.get("original_rows")
        if isinstance(cols, list) and isinstance(rows, int):
            return f"{rows}r × {len(cols)}c"
        if isinstance(rows, int):
            return pluralize(rows, "row")
        if isinstance(cols, list):
            n = len(cols)
            return f"{n} col" if n == 1 else f"{n} cols"
    return ""


def _fmt_validate_semantic(result: Any) -> str:
    if isinstance(result, dict):
        valid = result.get("valid")
        issues = result.get("issues") or []
        if valid is True:
            return "valid"
        if valid is False:
            n = len(issues) if isinstance(issues, list) else 0
            return f"{pluralize(n, 'issue')}" if n else "invalid"
    return ""


def _fmt_attribution_analyze(result: Any) -> str:
    if isinstance(result, dict):
        ranking = result.get("dimension_ranking") or []
        selected = result.get("selected_dimensions") or []
        n_sel = len(selected) if isinstance(selected, list) else 0
        n_rank = len(ranking) if isinstance(ranking, list) else 0
        if n_sel and n_rank:
            return f"sel {n_sel}/{n_rank} dims"
        if n_sel:
            return f"sel {n_sel} dim" if n_sel == 1 else f"sel {n_sel} dims"
    return ""


def _fmt_search_metrics(result: Any) -> str:
    if isinstance(result, list):
        n = len(result)
        return f"{n} metric hit" if n == 1 else f"{n} metric hits"
    return ""


def _fmt_search_reference_sql(result: Any) -> str:
    if isinstance(result, list):
        n = len(result)
        return f"{n} SQL hit" if n == 1 else f"{n} SQL hits"
    return ""


def _fmt_search_semantic_objects(result: Any) -> str:
    return _list_count(result, "object", "objects")


# === Generation / semantic-model-gen tools ===


def _fmt_check_semantic_object_exists(result: Any) -> str:
    if isinstance(result, dict):
        kind = result.get("kind") or "object"
        if result.get("exists") is True:
            return f"{kind} exists"
        if result.get("exists") is False:
            return f"{kind} not found"
    return ""


def _fmt_check_semantic_model_exists(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("exists") is True:
            return "table exists"
        if result.get("exists") is False:
            return "table not found"
    return ""


def _fmt_end_semantic_model_generation(result: Any) -> str:
    if isinstance(result, dict):
        files = result.get("semantic_model_files")
        if isinstance(files, list):
            n = len(files)
            return f"{n} semantic file" if n == 1 else f"{n} semantic files"
    return ""


def _fmt_end_metric_generation(result: Any) -> str:
    if isinstance(result, dict):
        sync = result.get("sync") or {}
        if isinstance(sync, dict) and sync.get("success"):
            return "metric synced"
        if result.get("metric_file"):
            return "metric generated"
    return ""


def _fmt_generate_sql_summary_id(result: Any) -> str:
    if isinstance(result, str) and result:
        return f"id: {result}"
    return ""


def _fmt_analyze_table_relationships(result: Any) -> str:
    if isinstance(result, dict):
        relationships = result.get("relationships")
        if isinstance(relationships, list) and relationships:
            n = len(relationships)
            return f"{n} rel" if n == 1 else f"{n} rels"
        summary = result.get("summary")
        if isinstance(summary, str) and summary:
            return summary
        if isinstance(relationships, list):
            return "0 rels"
    return ""


def _fmt_analyze_column_usage_patterns(result: Any) -> str:
    if isinstance(result, dict):
        patterns = result.get("column_patterns")
        if isinstance(patterns, dict) and patterns:
            n = len(patterns)
            return f"{n} col analyzed" if n == 1 else f"{n} cols analyzed"
        summary = result.get("summary")
        if isinstance(summary, str) and summary:
            return summary
    return ""


def _fmt_profile_semantic_model_evidence(result: Any) -> str:
    if isinstance(result, dict):
        tables = result.get("tables")
        if isinstance(tables, dict):
            n = len(tables)
            suffix = " + data" if result.get("data_profiled") else ""
            return (f"{n} table profiled" if n == 1 else f"{n} tables profiled") + suffix
        summary = result.get("summary")
        if isinstance(summary, str) and summary:
            return summary
    return ""


def _fmt_get_multiple_tables_ddl(result: Any) -> str:
    if isinstance(result, list):
        n = len(result)
        return f"DDL of {n} table" if n == 1 else f"DDL of {n} tables"
    return ""


def _fmt_analyze_metric_candidates_from_history(result: Any) -> str:
    if isinstance(result, dict):
        candidates = result.get("metric_candidates")
        if isinstance(candidates, list):
            n = len(candidates)
            suffix = ""
            if result.get("query_classification") == "metric_plus_derived_datasource":
                suffix = " + datasource"
            return (f"{n} metric cand" if n == 1 else f"{n} metric cands") + suffix
        summary = result.get("summary")
        if isinstance(summary, str) and summary:
            return summary
    return ""


# === Scheduler tools ===


def _fmt_submit_sql_job(result: Any) -> str:
    if isinstance(result, dict):
        job_id = result.get("job_id")
        if job_id:
            return f"+job {job_id}"
    return ""


def _fmt_submit_sparksql_job(result: Any) -> str:
    if isinstance(result, dict):
        job_id = result.get("job_id")
        if job_id:
            return f"+spark {job_id}"
    return ""


def _fmt_trigger_scheduler_job(result: Any) -> str:
    if isinstance(result, dict):
        run_id = result.get("run_id")
        job_id = result.get("job_id")
        if job_id and run_id:
            return f"{job_id}→{run_id}"
        if job_id:
            return f"trig {job_id}"
    return ""


def _fmt_get_scheduler_job(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("found") is False:
            return f"{result.get('job_id', '?')} not found"
        job_name = result.get("job_name")
        status = result.get("status")
        if job_name and status:
            return f"{job_name}: {status}"
        if result.get("job_id"):
            return f"job {result['job_id']}"
    return ""


def _fmt_list_scheduler_jobs(result: Any) -> str:
    return _envelope_with_label(result, "job", "jobs")


def _fmt_pause_job(result: Any) -> str:
    if isinstance(result, dict) and result.get("job_id"):
        return f"paused {result['job_id']}"
    return ""


def _fmt_resume_job(result: Any) -> str:
    if isinstance(result, dict) and result.get("job_id"):
        return f"resumed {result['job_id']}"
    return ""


def _fmt_delete_job(result: Any) -> str:
    if isinstance(result, dict) and result.get("job_id"):
        return f"deleted {result['job_id']}"
    return ""


def _fmt_update_job(result: Any) -> str:
    if isinstance(result, dict) and result.get("job_id"):
        return f"updated {result['job_id']}"
    return ""


def _fmt_list_job_runs(result: Any) -> str:
    return _envelope_with_label(result, "run", "runs")


def _fmt_get_run_log(result: Any) -> str:
    if isinstance(result, dict):
        run_id = result.get("run_id")
        log = result.get("log")
        if run_id and isinstance(log, str):
            lines = len(log.splitlines())
            return f"{run_id}: {lines} lines" if lines != 1 else f"{run_id}: 1 line"
        if run_id:
            return f"log: {run_id}"
    return ""


def _fmt_list_scheduler_connections(result: Any) -> str:
    if isinstance(result, dict) and isinstance(result.get("total"), int):
        n = result["total"]
        return f"{n} connection" if n == 1 else f"{n} connections"
    return ""


# === Context search tools ===


def _fmt_list_subject_tree(result: Any) -> str:
    """Walk the nested taxonomy and return the total leaf count."""
    if not isinstance(result, dict):
        return ""

    leaf_keys = {"metrics", "reference_sql", "reference_template"}
    total = 0

    def walk(node: Any) -> None:
        nonlocal total
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in leaf_keys:
                if isinstance(value, list):
                    total += len(value)
            elif isinstance(value, dict):
                walk(value)

    walk(result)
    if total == 0:
        return "subject tree empty"
    return f"{total} item" if total == 1 else f"{total} items"


def _fmt_get_metrics(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name")
        if name:
            return f'metric "{name}"'
    if isinstance(result, list):
        return _list_count(result, "metric", "metrics")
    return ""


def _fmt_get_reference_sql(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("name")
        if name:
            return f"SQL: {name}"
    if isinstance(result, list):
        n = len(result)
        return f"{n} SQL" if n == 1 else f"{n} SQLs"
    return ""


# === Reference template tools ===


def _fmt_search_reference_template(result: Any) -> str:
    return _list_count(result, "template", "templates")


def _fmt_get_reference_template(result: Any) -> str:
    if isinstance(result, dict) and result.get("name"):
        return f'template "{result["name"]}"'
    return ""


def _fmt_render_reference_template(result: Any) -> str:
    if isinstance(result, dict) and result.get("template_name"):
        return f'rendered "{result["template_name"]}"'
    return ""


def _fmt_execute_reference_template(result: Any) -> str:
    if isinstance(result, dict):
        name = result.get("template_name")
        query_result = result.get("query_result")
        rows: Optional[int] = None
        if isinstance(query_result, dict):
            rows = query_result.get("original_rows")
        if name and isinstance(rows, int):
            return f"{rows} rows: {name}"
        if name:
            return f'executed "{name}"'
    return ""


# === Filesystem tools (NOT clipped at exit) ===


def _fmt_read_file(result: Any) -> str:
    if isinstance(result, str):
        line_count = result.count("\n") + (1 if result and not result.endswith("\n") else 0)
        return f"read {pluralize(line_count, 'line')}"
    return ""


def _fmt_write_file(result: Any) -> str:
    if isinstance(result, str):
        marker = "File written successfully: "
        if result.startswith(marker):
            return f"wrote {result[len(marker) :]}"
        return truncate_text(result)
    return ""


def _fmt_edit_file(result: Any) -> str:
    if isinstance(result, str):
        marker = "File edited successfully: "
        if result.startswith(marker):
            return f"edited {result[len(marker) :]}"
        return truncate_text(result)
    return ""


def _fmt_delete_file(result: Any) -> str:
    if isinstance(result, str):
        marker = "File deleted successfully: "
        if result.startswith(marker):
            return f"deleted {result[len(marker) :]}"
        return truncate_text(result)
    return ""


def _fmt_glob(result: Any) -> str:
    if isinstance(result, dict):
        files = result.get("files")
        if isinstance(files, list):
            base = pluralize(len(files), "file")
            if result.get("truncated"):
                base = f"{base} (truncated)"
            return base
    return ""


def _fmt_grep(result: Any) -> str:
    if isinstance(result, dict):
        matches = result.get("matches")
        if isinstance(matches, list):
            base = pluralize(len(matches), "match") if len(matches) == 1 else f"{len(matches)} matches"
            if result.get("truncated"):
                base = f"{base} (truncated)"
            return base
    return ""


# === Plan / todo tools ===


def _fmt_todo_list(result: Any) -> str:
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, list):
            total = result.get("total", len(items))
            completed = result.get(
                "completed", sum(1 for it in items if isinstance(it, dict) and it.get("status") == "completed")
            )
            return f"{completed}/{total} todos"
    return ""


def _fmt_todo_read(result: Any) -> str:
    if isinstance(result, dict):
        title = result.get("title")
        status = result.get("status")
        if title and status:
            return f"{title}: {status}"
    return ""


def _fmt_todo_write(result: Any) -> str:
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, list):
            return f"{pluralize(len(items), 'todo')}"
    return ""


def _fmt_todo_update(result: Any) -> str:
    if isinstance(result, dict):
        item = result.get("updated_item") or {}
        if isinstance(item, dict):
            status = item.get("status")
            title = item.get("title")
            if status and title:
                return f"{title}: {status}"
            if status:
                return f"todo: {status}"
    return ""


# === Date / session tools ===


def _fmt_parse_temporal_expressions(result: Any) -> str:
    if isinstance(result, dict):
        dates = result.get("extracted_dates")
        if isinstance(dates, list):
            resolved: list[str] = []
            for item in dates:
                if not isinstance(item, dict):
                    continue
                start = _clean_input_text(item.get("start"), limit=32)
                end = _clean_input_text(item.get("end"), limit=32)
                compact_end = end[5:] if start[:4] == end[:4] and len(start) >= 10 and len(end) >= 10 else end
                date_range = "～".join(part for part in (start, compact_end) if part)
                if date_range:
                    resolved.append(date_range)
            if resolved:
                return f"{resolved[0]} +{len(resolved) - 1}" if len(resolved) > 1 else resolved[0]
            return f"parsed {len(dates)} dates"
    return ""


def _fmt_get_current_date(result: Any) -> str:
    if isinstance(result, dict) and result.get("current_date"):
        return str(result["current_date"])
    return ""


def _fmt_search_skill_usage(result: Any) -> str:
    if isinstance(result, dict):
        matches = result.get("matches")
        if isinstance(matches, list):
            return _list_count(matches, "session", "sessions")
    return ""


# === Skill tools ===


def _fmt_load_skill(result: Any) -> str:
    if isinstance(result, dict):
        metadata = result.get("metadata") or {}
        name = metadata.get("name") or result.get("name")
        if name:
            return f"+{name}"
    return ""


def _fmt_validate_skill(result: Any) -> str:
    if isinstance(result, dict):
        skill_name = result.get("skill_name") or "skill"
        warnings = result.get("warnings", 0)
        if warnings:
            return f"{skill_name} valid ({warnings} warns)"
        return f"{skill_name} valid"
    return ""


# === Ask user / interaction ===


def _fmt_ask_user(result: Any) -> str:
    """``ask_user`` stores answers as a JSON-encoded string list."""
    text: Optional[str] = None
    if isinstance(result, str) and result.strip():
        text = result
    elif isinstance(result, dict):
        text = result.get("content") or result.get("answer")
    if not text:
        return ""
    try:
        decoded = json.loads(text) if isinstance(text, str) and text.lstrip().startswith("[") else None
    except (TypeError, ValueError):
        decoded = None
    if isinstance(decoded, list) and decoded:
        first = decoded[0]
        if isinstance(first, dict):
            ans = first.get("answer")
            if ans is not None:
                preview = ans if isinstance(ans, str) else str(ans)
                if len(decoded) > 1:
                    return f"{preview} +{len(decoded) - 1}"
                return f'"{preview}"'
        return f"{len(decoded)} answers"
    if isinstance(text, str):
        return f'"{text}"'
    return ""


# === Sub-agent task tool ===


def _fmt_task(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    if result.get("sql_file_path"):
        return "SQL file generated"
    if result.get("sql"):
        return "SQL generated"
    semantic_models = result.get("semantic_models")
    if isinstance(semantic_models, list):
        n = len(semantic_models)
        return f"{n} semantic model" if n == 1 else f"{n} semantic models"
    if result.get("sql_summary_file"):
        return "SQL summary saved"
    if result.get("report_result") is not None:
        return "report ready"
    skill_name = result.get("skill_name")
    if result.get("skill_path"):
        return f'skill "{skill_name}" generated' if skill_name else "skill generated"
    if result.get("dashboard_result") is not None:
        return "dashboard updated"
    if result.get("scheduler_result") is not None:
        return "scheduler updated"
    if result.get("items_saved") is not None:
        return "feedback saved"
    response = result.get("response")
    if isinstance(response, str) and response.strip():
        return f'"{response}"'
    return ""


# === Platform doc search ===


def _fmt_list_document_nav(result: Any) -> str:
    if isinstance(result, dict):
        platform = result.get("platform") or ""
        total = result.get("total_docs")
        if isinstance(total, int):
            base = pluralize(total, "doc")
            return f"{platform}: {base}" if platform else base
    return ""


def _fmt_get_document(result: Any) -> str:
    if isinstance(result, dict):
        platform = result.get("platform") or ""
        chunks = result.get("chunk_count")
        if chunks is None and isinstance(result.get("chunks"), list):
            chunks = len(result["chunks"])
        if isinstance(chunks, int):
            base = pluralize(chunks, "chunk")
            return f"{platform}: {base}" if platform else base
    return ""


def _fmt_search_document(result: Any) -> str:
    if isinstance(result, dict):
        n = result.get("doc_count")
        if n is None and isinstance(result.get("docs"), list):
            n = len(result["docs"])
        if isinstance(n, int):
            return pluralize(n, "doc match") if n == 1 else f"{n} doc matches"
    return ""


def _fmt_web_search(result: Any) -> str:
    # Canonical schema (datus.schemas.web_result): {query, result_count, results}.
    from datus.schemas.web_result import web_search_short_summary

    if isinstance(result, dict) and ("results" in result or "query" in result):
        return web_search_short_summary(result)
    # Legacy fallbacks (older docs/doc_count shape, or a bare list).
    if isinstance(result, list):
        return pluralize(len(result), "web result")
    if isinstance(result, dict):
        n = result.get("doc_count")
        if n is None and isinstance(result.get("docs"), list):
            n = len(result["docs"])
        if isinstance(n, int):
            return pluralize(n, "web result")
    return ""


def _fmt_web_fetch(result: Any) -> str:
    from datus.schemas.web_result import web_fetch_short_summary

    if isinstance(result, dict) and isinstance(result.get("content"), str):
        return web_fetch_short_summary(result)
    return ""


# ── Registry ────────────────────────────────────────────────────────────


FormatterFn = Callable[[Any], str]


class ToolSummaryRegistry:
    """Centralized per-tool success-summary registry.

    Failure summaries are produced uniformly by :func:`format_failure`;
    per-tool formatters are invoked only when the payload indicates
    success and the unwrapped ``result`` is non-empty.

    The registry exit applies :func:`_clip_short` so every non-filesystem
    summary is bounded to ``SUMMARY_TEXT_MAX_CHARS`` characters.
    """

    def __init__(self) -> None:
        self._formatters: Dict[str, FormatterFn] = {}

    def register(self, tool_name: str, fn: FormatterFn) -> None:
        self._formatters[tool_name] = fn

    def has(self, tool_name: str) -> bool:
        return tool_name in self._formatters

    def names(self) -> list:
        return sorted(self._formatters.keys())

    def summarize_dict(self, data: Any, tool_name: str = "") -> str:
        """Build a one-line summary from a FuncToolResult-shaped dict."""
        if not isinstance(data, dict):
            raw = format_generic_result(data) if data is not None else "Empty result"
            return _clip_short(raw, tool_name)

        if looks_like_failure(data):
            return _clip_short(format_failure(data), tool_name)

        result_value = data["result"] if "result" in data else data

        if is_empty_result(result_value):
            return _clip_short("Empty result", tool_name)

        formatter = self._formatters.get(tool_name)
        if formatter is not None:
            try:
                summary = formatter(result_value)
                if summary:
                    return _clip_short(summary, tool_name)
            except Exception as fmt_err:  # pragma: no cover - defensive
                logger.debug(f"Tool summary formatter for {tool_name} raised: {fmt_err}")

        return _clip_short(format_generic_result(result_value), tool_name)

    def summarize_content(self, content: str, tool_name: str = "") -> str:
        """Build a summary from a tool result string (MCP / legacy adapters)."""
        if not content:
            return _clip_short("Empty result", tool_name)

        try:
            data = json.loads(content)
        except (TypeError, ValueError):
            return _clip_short(truncate_text(content), tool_name)

        if isinstance(data, dict):
            return self.summarize_dict(data, tool_name)
        if isinstance(data, list):
            return _clip_short(pluralize(len(data), "item"), tool_name)
        if isinstance(data, bool):
            return _clip_short("OK" if data else "Failed", tool_name)
        if isinstance(data, int):
            return _clip_short(pluralize(data, "row"), tool_name)
        return _clip_short(truncate_text(str(data)), tool_name)


def _register_builtins(registry: ToolSummaryRegistry) -> None:
    """Register every built-in tool formatter."""
    builtins: Dict[str, FormatterFn] = {
        # Database tools
        "execute_sql": _fmt_execute_sql,
        "read_query": _fmt_read_query,
        "query": _fmt_read_query,
        "execute_write": _fmt_execute_write,
        "execute_ddl": _fmt_execute_ddl,
        "describe_table": _fmt_describe_table,
        "list_tables": _fmt_list_tables,
        "table_overview": _fmt_list_tables,
        "list_databases": _fmt_list_databases,
        "list_schemas": _fmt_list_schemas,
        "search_table": _fmt_search_table,
        "transfer_query_result": _fmt_transfer_query_result,
        # BI tools
        "list_dashboards": _fmt_list_dashboards,
        "get_dashboard": _fmt_get_dashboard,
        "list_charts": _fmt_list_charts,
        "get_chart": _fmt_get_chart,
        "get_chart_data": _fmt_get_chart_data,
        "list_datasets": _fmt_list_datasets,
        "create_dashboard": _fmt_create_dashboard,
        "update_dashboard": _fmt_update_dashboard,
        "delete_dashboard": _fmt_delete_dashboard,
        "create_chart": _fmt_create_chart,
        "update_chart": _fmt_update_chart,
        "add_chart_to_dashboard": _fmt_add_chart_to_dashboard,
        "delete_chart": _fmt_delete_chart,
        "create_dataset": _fmt_create_dataset,
        "list_bi_databases": _fmt_list_bi_databases,
        "delete_dataset": _fmt_delete_dataset,
        "write_query": _fmt_write_query,
        # Semantic tools
        "list_metrics": _fmt_list_metrics,
        "get_dimensions": _fmt_get_dimensions,
        "query_metrics": _fmt_query_metrics,
        "validate_semantic": _fmt_validate_semantic,
        "attribution_analyze": _fmt_attribution_analyze,
        "search_metrics": _fmt_search_metrics,
        "search_reference_sql": _fmt_search_reference_sql,
        "search_semantic_objects": _fmt_search_semantic_objects,
        # Generation / semantic discovery
        "check_semantic_object_exists": _fmt_check_semantic_object_exists,
        "check_semantic_model_exists": _fmt_check_semantic_model_exists,
        "end_semantic_model_generation": _fmt_end_semantic_model_generation,
        "end_metric_generation": _fmt_end_metric_generation,
        "generate_sql_summary_id": _fmt_generate_sql_summary_id,
        "analyze_table_relationships": _fmt_analyze_table_relationships,
        "analyze_column_usage_patterns": _fmt_analyze_column_usage_patterns,
        "profile_semantic_model_evidence": _fmt_profile_semantic_model_evidence,
        "analyze_metric_candidates_from_history": _fmt_analyze_metric_candidates_from_history,
        "get_multiple_tables_ddl": _fmt_get_multiple_tables_ddl,
        # Scheduler tools
        "submit_sql_job": _fmt_submit_sql_job,
        "submit_sparksql_job": _fmt_submit_sparksql_job,
        "trigger_scheduler_job": _fmt_trigger_scheduler_job,
        "get_scheduler_job": _fmt_get_scheduler_job,
        "list_scheduler_jobs": _fmt_list_scheduler_jobs,
        "pause_job": _fmt_pause_job,
        "resume_job": _fmt_resume_job,
        "delete_job": _fmt_delete_job,
        "delete_scheduler_job": _fmt_delete_job,
        "update_job": _fmt_update_job,
        "list_job_runs": _fmt_list_job_runs,
        "get_run_log": _fmt_get_run_log,
        "list_scheduler_connections": _fmt_list_scheduler_connections,
        # Context search
        "list_subject_tree": _fmt_list_subject_tree,
        "get_metrics": _fmt_get_metrics,
        "get_reference_sql": _fmt_get_reference_sql,
        # Reference templates
        "search_reference_template": _fmt_search_reference_template,
        "get_reference_template": _fmt_get_reference_template,
        "render_reference_template": _fmt_render_reference_template,
        "execute_reference_template": _fmt_execute_reference_template,
        # Filesystem
        "read_file": _fmt_read_file,
        "write_file": _fmt_write_file,
        "edit_file": _fmt_edit_file,
        "delete_file": _fmt_delete_file,
        "glob": _fmt_glob,
        "grep": _fmt_grep,
        # Plan / todo
        "todo_list": _fmt_todo_list,
        "todo_read": _fmt_todo_read,
        "todo_write": _fmt_todo_write,
        "todo_update": _fmt_todo_update,
        # Date / session
        "parse_temporal_expressions": _fmt_parse_temporal_expressions,
        "get_current_date": _fmt_get_current_date,
        "search_skill_usage": _fmt_search_skill_usage,
        # Skill
        "load_skill": _fmt_load_skill,
        "validate_skill": _fmt_validate_skill,
        # Ask user
        "ask_user": _fmt_ask_user,
        # Sub-agent task
        "task": _fmt_task,
        # Platform doc search
        "list_document_nav": _fmt_list_document_nav,
        "get_document": _fmt_get_document,
        "search_document": _fmt_search_document,
        "web_search": _fmt_web_search,
        "web_fetch": _fmt_web_fetch,
    }
    for name, fn in builtins.items():
        registry.register(name, fn)


TOOL_SUMMARY_REGISTRY = ToolSummaryRegistry()
_register_builtins(TOOL_SUMMARY_REGISTRY)

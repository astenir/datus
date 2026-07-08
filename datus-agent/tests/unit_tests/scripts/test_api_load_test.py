from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_tool():
    path = Path(__file__).resolve().parents[3] / "scripts" / "api_load_test.py"
    spec = importlib.util.spec_from_file_location("api_load_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    base = {
        "scenario": "catalog",
        "datasource": "ccks_fund",
        "sql": "SELECT 1",
        "result_format": "json",
        "database": "",
        "message": "hi",
        "session_id": "",
        "stream_response": False,
        "max_turns": 6,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_catalog_endpoint_uses_datasource_query_param():
    tool = _load_tool()

    call = tool._endpoint_for_request(_args(scenario="catalog", datasource="ccks_fund"), 0)

    assert call.name == "catalog"
    assert call.method == "GET"
    assert call.path == "/api/v1/catalog/list"
    assert call.params == {"datasource_id": "ccks_fund"}


def test_sql_endpoint_uses_caller_sql_and_unique_task_id():
    tool = _load_tool()

    call = tool._endpoint_for_request(_args(scenario="sql", sql="SELECT 42", database="demo"), 3)

    assert call.name == "sql"
    assert call.method == "POST"
    assert call.path == "/api/v1/sql/execute"
    assert call.json_body["sql_query"] == "SELECT 42"
    assert call.json_body["database_name"] == "demo"
    assert call.json_body["execute_task_id"].startswith("load-3-")


def test_chat_endpoint_defaults_to_distinct_sessions():
    tool = _load_tool()

    first = tool._endpoint_for_request(_args(scenario="chat", datasource="ccks_fund"), 1)
    second = tool._endpoint_for_request(_args(scenario="chat", datasource="ccks_fund"), 2)

    assert first.stream is True
    assert first.json_body["datasource"] == "ccks_fund"
    assert first.json_body["interactive"] is False
    assert first.json_body["session_id"] != second.json_body["session_id"]


def test_percentile_interpolates():
    tool = _load_tool()

    assert tool._percentile([10, 20, 30], 0.5) == 20
    assert tool._percentile([10, 20], 0.95) == 19.5


def test_summary_counts_statuses_and_errors():
    tool = _load_tool()

    results = [
        tool.CallResult(name="catalog", ok=True, status_code=200, latency_ms=10, bytes_read=5),
        tool.CallResult(name="catalog", ok=False, status_code=500, latency_ms=30, error="boom"),
    ]
    summary = tool._summarize(results, elapsed_s=2)

    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["requests_per_second"] == 1
    assert summary["status_counts"] == {"200": 1, "500": 1}
    assert summary["sample_errors"] == ["boom"]

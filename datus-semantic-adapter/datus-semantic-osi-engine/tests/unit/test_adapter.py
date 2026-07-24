# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Adapter behavior against the fake binding: query construction, slicing,
dry-run shape, engine lifecycle, and connections wiring."""

from __future__ import annotations

import os

import pytest
import yaml
from _fakes import FakeEngine

from datus_semantic_osi_engine.errors import SemanticValidationException


async def test_list_metrics_maps_rows_and_slices(make_adapter):
    adapter = make_adapter()
    metrics = await adapter.list_metrics()
    assert [m.name for m in metrics] == ["order_count", "revenue"]
    assert metrics[0].type == "aggregate"
    assert metrics[0].measures == ["order_count"]
    assert metrics[0].metadata == {"datasets": ["orders"]}
    assert "orders.status" in metrics[0].dimensions

    assert [m.name for m in await adapter.list_metrics(limit=1)] == ["order_count"]
    assert [m.name for m in await adapter.list_metrics(limit=5, offset=1)] == ["revenue"]


async def test_get_dimensions_returns_all_and_flags_time(make_adapter):
    adapter = make_adapter()
    dims = {d.name: d for d in await adapter.get_dimensions("revenue")}
    assert set(dims) == {"orders.status", "orders.order_date", "customers.region"}
    assert dims["orders.order_date"].type == "time"
    assert dims["orders.status"].type is None


async def test_get_dimensions_unknown_metric_is_structured(make_adapter):
    adapter = make_adapter()
    with pytest.raises(SemanticValidationException) as exc:
        await adapter.get_dimensions("revenues")
    payload = exc.value.payload
    assert payload.code == "unknown_metric"
    assert payload.metrics == ["revenues"]
    assert "order_count" in payload.message


async def test_query_metrics_builds_metric_query(make_adapter):
    adapter = make_adapter()
    await adapter.query_metrics(
        metrics=["revenue"],
        dimensions=["orders.status", "orders.order_date"],
        time_start="2025-01-01",
        time_end="2025-02-01",
        time_granularity="month",
        where="status <> 'void'",
        limit=10,
        order_by=["-revenue", "status"],
    )
    engine = FakeEngine.instances[-1]
    (call,) = engine.execute_calls
    assert call["query"] == {
        "metrics": ["revenue"],
        "group_by": [
            {"field": "orders.status"},
            {"field": "orders.order_date", "grain": "month"},
        ],
        "where_sql": "status <> 'void'",
        "time_range": {"start": "2025-01-01", "end": "2025-02-01"},
        "order_by": [
            {"key": "revenue", "desc": True},
            {"key": "status", "desc": False},
        ],
        "limit": 10,
    }
    assert call["timeout_secs"] == 30.0
    assert call["connection"] is None


async def test_query_metrics_bare_time_dimension_gets_grain(make_adapter):
    adapter = make_adapter()
    await adapter.query_metrics(
        metrics=["revenue"], dimensions=["order_date"], time_granularity="day"
    )
    engine = FakeEngine.instances[-1]
    assert engine.execute_calls[0]["query"]["group_by"] == [
        {"field": "order_date", "grain": "day"}
    ]


async def test_time_range_without_time_grouping_binds_metric_time_dimension(make_adapter):
    """A time filter with no time grouping resolves the metric's time dimension.

    The engine otherwise rejects the query with time_range_needs_dimension —
    but "total for September" style asks are the most common Datus shape.
    """
    adapter = make_adapter()
    await adapter.query_metrics(metrics=["revenue"], time_start="2025-09-01", time_end="2025-10-01")
    engine = FakeEngine.instances[-1]
    assert engine.execute_calls[0]["query"]["time_range"] == {
        "start": "2025-09-01",
        "end": "2025-10-01",
        "dimension": "orders.order_date",
    }


def test_time_range_with_ambiguous_time_dimensions_is_structured(make_adapter):
    adapter = make_adapter()
    with pytest.raises(SemanticValidationException) as exc:
        adapter._build_query(
            [
                {"name": "orders.order_date", "is_time": True},
                {"name": "orders.ship_date", "is_time": True},
            ],
            [{"name": "revenue", "datasets": ["orders"]}],
            metrics=["revenue"],
            dimensions=[],
            time_start="2025-09-01",
            time_end="2025-10-01",
            time_granularity=None,
            where=None,
            limit=None,
            order_by=None,
        )
    payload = exc.value.payload
    assert payload.code == "time_range_needs_dimension"
    assert payload.required_dimensions == ["orders.order_date", "orders.ship_date"]


def test_time_range_with_no_reachable_time_dimension_stays_unbound(make_adapter):
    """No candidate: pass the range through; the engine reports its own error."""
    adapter = make_adapter()
    query = adapter._build_query(
        [{"name": "orders.status", "is_time": False}],
        [{"name": "revenue", "datasets": ["orders"]}],
        metrics=["revenue"],
        dimensions=[],
        time_start="2025-09-01",
        time_end="2025-10-01",
        time_granularity=None,
        where=None,
        limit=None,
        order_by=None,
    )
    assert query["time_range"] == {"start": "2025-09-01", "end": "2025-10-01"}


async def test_time_granularity_without_time_dimension_is_structured(make_adapter):
    adapter = make_adapter()
    with pytest.raises(SemanticValidationException) as exc:
        await adapter.query_metrics(
            metrics=["revenue"], dimensions=["orders.status"], time_granularity="day"
        )
    payload = exc.value.payload
    assert payload.code == "time_grain_required"
    assert payload.required_dimensions == ["orders.order_date"]
    assert payload.suggested_retry == {
        "metrics": ["revenue"],
        "dimensions": ["orders.status", "orders.order_date"],
        "time_granularity": "day",
    }


async def test_dry_run_returns_sql_contract(make_adapter):
    adapter = make_adapter(db_config={"type": "postgresql"})
    result = await adapter.query_metrics(metrics=["revenue"], dry_run=True)
    assert result.columns == ["sql"]
    assert result.data == [{"sql": "SELECT 1 AS compiled"}]
    assert result.metadata["dry_run"] is True
    assert result.metadata["sql"] == "SELECT 1 AS compiled"
    engine = FakeEngine.instances[-1]
    (call,) = engine.compile_calls
    # postgresql (Datus vocabulary) normalized to postgres (engine dialect)
    assert call["dialect"] == "postgres"
    assert not engine.execute_calls


async def test_execute_result_maps_to_query_result(make_adapter):
    adapter = make_adapter()
    result = await adapter.query_metrics(metrics=["order_count"], dimensions=["orders.status"])
    assert result.columns == ["status", "order_count"]
    assert result.data == [{"status": "paid", "order_count": 2}]
    assert result.metadata["row_count"] == 1
    assert "sql" in result.metadata


async def test_engine_rebuilds_on_model_mtime_change(make_adapter, model_file):
    adapter = make_adapter()
    await adapter.list_metrics()
    await adapter.list_metrics()
    assert len(FakeEngine.instances) == 1

    model_file.write_text("version: '0.2.0.dev0'\nsemantic_model: []\n# touched\n")
    os.utime(model_file, (0, 0))  # force a different mtime regardless of clock
    await adapter.list_metrics()
    assert len(FakeEngine.instances) == 2


async def test_db_config_written_as_datasources_yaml(make_adapter):
    adapter = make_adapter(
        db_config={"type": "postgresql", "host": "db.local", "port": 5432},
        datasource="warehouse",
    )
    await adapter.query_metrics(metrics=["revenue"])
    engine = FakeEngine.instances[-1]
    assert engine.execute_calls[0]["connection"] == "warehouse"
    with open(engine.connections_path, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    assert payload == {
        "datasources": {
            "warehouse": {
                "type": "postgres",
                "host": "db.local",
                "port": 5432,
                "default": True,
            }
        }
    }


async def test_explicit_connections_path_wins(make_adapter, tmp_path):
    connections = tmp_path / "agent.yml"
    connections.write_text("datasources: {}\n")
    adapter = make_adapter(
        connections_path=str(connections),
        db_config={"type": "mysql"},
        connection="prod",
    )
    await adapter.query_metrics(metrics=["revenue"])
    engine = FakeEngine.instances[-1]
    assert engine.connections_path == str(connections)
    assert engine.execute_calls[0]["connection"] == "prod"


def test_list_semantic_models_maps_datasets(make_adapter):
    adapter = make_adapter()
    models = adapter.list_semantic_models()
    assert [m.name for m in models] == ["orders", "customers"]
    assert models[0].table_name == "main.orders"
    assert models[0].extra["primary_key"] == ["order_id"]

    assert adapter.get_semantic_model("orders").name == "orders"
    assert adapter.get_semantic_model("main.customers").name == "customers"
    assert adapter.get_semantic_model("nope") is None


async def test_validate_semantic_maps_issues(make_adapter, fake_binding):
    def failing_validate(text):
        return {
            "valid": False,
            "issues": [
                {
                    "severity": "warning",
                    "code": "missing_sql_dialect",
                    "location": "semantic_model[0]",
                    "message": "field has no SQL dialect",
                }
            ],
            "compile_errors": [
                {
                    "code": "unknown_column",
                    "location": "metrics[0]",
                    "message": "no such column",
                    "hint": "did you mean amount?",
                }
            ],
        }

    fake_binding.validate = failing_validate
    adapter = make_adapter()
    result = await adapter.validate_semantic()
    assert result.valid is False
    assert len(result.issues) == 2
    assert result.issues[0].severity == "warning"
    assert result.issues[0].location == "semantic_model[0]"
    assert "unknown_column" in result.issues[1].message
    assert "did you mean amount?" in result.issues[1].message


async def test_validate_semantic_ok(make_adapter):
    adapter = make_adapter()
    result = await adapter.validate_semantic()
    assert result.valid is True
    assert result.issues == []


async def test_semantic_models_path_directory_single_file(tmp_path):
    from datus_semantic_osi_engine.adapter import OSIEngineAdapter
    from datus_semantic_osi_engine.config import OSIEngineConfig

    (tmp_path / "model.yaml").write_text("version: '0.2.0.dev0'\nsemantic_model: []\n")
    adapter = OSIEngineAdapter(OSIEngineConfig(semantic_models_path=str(tmp_path)))
    await adapter.list_metrics()  # builds the engine
    assert FakeEngine.instances[-1].model_path == str(tmp_path / "model.yaml")


async def test_semantic_models_path_directory_multiple_is_error(tmp_path):
    from datus_semantic_core.exceptions import SemanticCoreException
    from datus_semantic_osi_engine.adapter import OSIEngineAdapter
    from datus_semantic_osi_engine.config import OSIEngineConfig

    (tmp_path / "a.yaml").write_text("version: '0.2.0.dev0'\nsemantic_model: []\n")
    (tmp_path / "b.yaml").write_text("version: '0.2.0.dev0'\nsemantic_model: []\n")
    adapter = OSIEngineAdapter(OSIEngineConfig(semantic_models_path=str(tmp_path)))
    with pytest.raises(SemanticCoreException, match="set semantic_model_path"):
        await adapter.list_metrics()

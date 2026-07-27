# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""End-to-end adapter tests against the real engine and a seeded DuckDB file."""

from __future__ import annotations

import shutil

import pytest

from datus_semantic_osi_engine.adapter import OSIEngineAdapter
from datus_semantic_osi_engine.config import OSIEngineConfig
from datus_semantic_osi_engine.errors import SemanticValidationException


def _real_binding_available() -> bool:
    try:
        import datus_osi_engine
    except ImportError:
        return False
    # The unit-test fake sets this marker; the real extension does not.
    return not getattr(datus_osi_engine, "__osi_fake__", False)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _real_binding_available(),
        reason="real datus-osi-engine bindings not installed",
    ),
    pytest.mark.skipif(shutil.which("duckdb") is None, reason="duckdb CLI not installed"),
]


def _adapter(model_path: str, seeded_db: str | None = None) -> OSIEngineAdapter:
    kwargs = {"semantic_model_path": model_path}
    if seeded_db is not None:
        kwargs["db_config"] = {"type": "duckdb", "uri": seeded_db}
    return OSIEngineAdapter(OSIEngineConfig(**kwargs))


async def test_list_metrics_and_dimensions(model_path):
    adapter = _adapter(model_path)
    names = {m.name for m in await adapter.list_metrics()}
    assert {"revenue", "order_count", "unique_customers"} <= names

    dims = {d.name: d for d in await adapter.get_dimensions("revenue")}
    assert "orders.order_date" in dims and dims["orders.order_date"].type == "time"
    assert "customers.region" in dims


async def test_dry_run_emits_sql(model_path):
    adapter = _adapter(model_path)
    result = await adapter.query_metrics(
        metrics=["revenue"], dimensions=["orders.status"], dry_run=True
    )
    assert result.columns == ["sql"]
    sql = result.data[0]["sql"]
    assert "main.orders" in sql
    assert result.metadata["dry_run"] is True


async def test_execute_returns_rows(model_path, seeded_db):
    adapter = _adapter(model_path, seeded_db)
    result = await adapter.query_metrics(
        metrics=["revenue"],
        dimensions=["orders.status"],
        order_by=["-revenue"],
    )
    assert result.metadata["row_count"] > 0
    assert result.columns == ["status", "revenue"]
    by_status = {r["status"]: r["revenue"] for r in result.data}
    # Oracle from the seed: completed=350, cancelled=100.
    assert by_status["completed"] == 350
    assert by_status["cancelled"] == 100


async def test_execute_with_time_grain(model_path, seeded_db):
    adapter = _adapter(model_path, seeded_db)
    result = await adapter.query_metrics(
        metrics=["revenue"],
        dimensions=["orders.order_date"],
        time_granularity="month",
    )
    assert "order_date__month" in result.columns
    assert result.metadata["row_count"] > 0


async def test_ambiguous_dimension_is_structured(model_path):
    adapter = _adapter(model_path)
    with pytest.raises(SemanticValidationException) as exc:
        # customer_id exists on both orders and customers.
        await adapter.query_metrics(metrics=["revenue"], dimensions=["customer_id"], dry_run=True)
    payload = exc.value.payload
    assert payload.code == "ambiguous_dimension"
    assert "customer_id" in payload.message


async def test_unknown_metric_is_structured(model_path):
    adapter = _adapter(model_path)
    with pytest.raises(SemanticValidationException) as exc:
        await adapter.query_metrics(metrics=["revenues"], dry_run=True)
    assert exc.value.payload.code == "unknown_metric"


async def test_validate_semantic_ok(model_path):
    adapter = _adapter(model_path)
    result = await adapter.validate_semantic()
    assert result.valid is True
    assert result.issues == []

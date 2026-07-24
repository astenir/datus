# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""DatusOSIAdapter end-to-end (DB-free): load OSI -> validate / list / dry-run."""

import pytest
import yaml
from types import SimpleNamespace
from typing import ClassVar

pytest.importorskip("metricflow")

from datus_semantic_core.models import QueryResult, ValidationResult
from datus_semantic_osi.adapter import DatusOSIAdapter
from datus_semantic_osi.backend import MetricFlowBackend
from datus_semantic_osi.config import DatusOSIConfig
from datus_semantic_osi.profile import parse_osi_profile, to_core_schema_document


def _core_yaml(legacy_profile: str) -> str:
    return yaml.safe_dump(
        to_core_schema_document(parse_osi_profile(legacy_profile)),
        sort_keys=False,
        allow_unicode=True,
    )


OSI_YAML = """
semantic_model:
  name: commerce_orders
datasets:
  - name: orders
    source:
      table: fact_orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
    dimensions:
      - name: order_channel
        expr: order_channel
metrics:
  - name: order_count
    description: "Order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    subject_path: [commerce, orders]
  - name: average_order_amount
    description: "Average order amount"
    expression: "AVG(order_amount)"
    dataset: orders
    subject_path: [commerce, orders]
  - name: running_order_count
    description: "Running order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    grain_to_date: month
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: sum
    subject_path: [commerce, orders]
  - name: moving_3_month_order_count_avg
    description: "Three-month moving average of order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    window: 3 months
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: avg
    subject_path: [commerce, orders]
  - name: rolling_order_count_level
    description: "Rolling order count level"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    window: 3 months
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: avg
    subject_path: [commerce, orders]
  - name: moving_window_month_count
    description: "Number of months in the moving window"
    expression: "COUNT(*)"
    dataset: orders
    window: 3 months
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: row_count
    subject_path: [commerce, orders]
  - name: running_min_average_order_amount
    description: "Running minimum of monthly average order amount"
    expression: "AVG(order_amount)"
    dataset: orders
    grain_to_date: month
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: min
    subject_path: [commerce, orders]
  - name: running_max_average_order_amount
    description: "Running maximum of monthly average order amount"
    expression: "AVG(order_amount)"
    dataset: orders
    grain_to_date: month
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: max
    subject_path: [commerce, orders]
  - name: order_count_mom
    description: "Month-over-month order count ratio"
    metric_kind: derived
    expression: "(order_count - order_count_prev) / NULLIF(order_count_prev, 0)"
    inputs:
      - name: order_count
      - name: order_count
        alias: order_count_prev
        offset_window: "1 month"
    subject_path: [commerce, orders]
  - name: previous_month_order_count
    description: "Previous month order count"
    metric_kind: derived
    expression: "previous_month_order_count"
    inputs:
      - name: order_count
        alias: previous_month_order_count
        offset_window: "1 month"
    subject_path: [commerce, orders]
  - name: order_count_month_yoy
    description: "Monthly year-over-year order count growth rate"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    period_over_period:
      time_grain: month
      offset_window: "1 year"
      calculation: percent_change
    subject_path: [commerce, orders]
  - name: order_count_week_wow_delta
    description: "Weekly week-over-week order count delta"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    period_over_period:
      time_grain: week
      offset_window: "1 week"
      calculation: delta
    subject_path: [commerce, orders]
  - name: running_week_order_count
    description: "Running weekly order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    grain_to_date: week
    custom_extensions:
      - vendor_name: DATUS
        data:
          window_aggregation: sum
    subject_path: [commerce, orders]
"""


SECOND_OSI_YAML = """
semantic_model:
  name: finance_budget
datasets:
  - name: budgets
    source:
      table: fact_budget
    primary_key: budget_id
    dimensions:
      - name: cost_center
        expr: cost_center
metrics:
  - name: budget_total
    description: "Budget total"
    expression: "SUM(budget_amount)"
    dataset: budgets
    subject_path: [finance, budget]
"""


@pytest.fixture
def adapter(tmp_path):
    (tmp_path / "model.yaml").write_text(_core_yaml(OSI_YAML))
    config = DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="starrocks")
    return DatusOSIAdapter(config)


@pytest.fixture
def multi_model_adapter(tmp_path):
    models_path = tmp_path / "models"
    models_path.mkdir()
    (models_path / "commerce_orders.yaml").write_text(_core_yaml(OSI_YAML))
    (models_path / "finance_budget.yaml").write_text(_core_yaml(SECOND_OSI_YAML))
    config = DatusOSIConfig(
        semantic_models_path=str(models_path), datasource="starrocks"
    )
    return DatusOSIAdapter(config)


class _FakeExecutor:
    def __init__(self, result=None, sql_rows=None):
        self.result = result or QueryResult()
        self.calls = []
        self.client = SimpleNamespace(sql_client=SimpleNamespace(query=self._query_sql))
        self.sql_rows = sql_rows or []
        self.sql_queries = []

    async def query_metrics(self, metrics, **kwargs):
        self.calls.append({"metrics": list(metrics), **kwargs})
        return self.result

    def _query_sql(self, sql):
        self.sql_queries.append(sql)
        return self.sql_rows


class _FakeBackend:
    has_live_connection = True

    def __init__(self, executor):
        self.executor = executor
        self.models = []

    def make_executor(self, model):
        self.models.append(model)
        return self.executor


class _FakeValidationBackend:
    has_live_connection = False
    capabilities: ClassVar[dict] = {}

    def __init__(self):
        self.models = []

    def validate(self, model):
        self.models.append(model)
        return ValidationResult(valid=True)


async def test_multi_model_adapter_lists_models_and_metrics(multi_model_adapter):
    models = multi_model_adapter.list_semantic_models()
    metrics = {
        metric.name: metric for metric in await multi_model_adapter.list_metrics()
    }

    assert {model.name for model in models} == {"commerce_orders", "finance_budget"}
    assert metrics["order_count"].metadata["semantic_model_name"] == "commerce_orders"
    assert metrics["budget_total"].metadata["semantic_model_name"] == "finance_budget"


async def test_multi_model_adapter_routes_query_to_metric_owner(multi_model_adapter):
    executor = _FakeExecutor(QueryResult(columns=["budget_total"], data=[]))
    backend = _FakeBackend(executor)
    multi_model_adapter._backend = backend

    await multi_model_adapter.query_metrics(["budget_total"])

    assert [model.name for model in backend.models] == ["finance_budget"]


async def test_multi_model_adapter_rejects_cross_model_query(multi_model_adapter):
    with pytest.raises(ValueError, match="multiple semantic models"):
        await multi_model_adapter.query_metrics(["order_count", "budget_total"])


async def test_targeted_validation_only_validates_selected_model(multi_model_adapter):
    backend = _FakeValidationBackend()
    multi_model_adapter._backend = backend

    result = await multi_model_adapter.validate_semantic(
        scope="semantic_model",
        semantic_model_name="finance_budget",
        checks=["backend"],
    )

    assert result.valid
    assert [model.name for model in backend.models] == ["finance_budget"]


async def test_targeted_validation_ignores_unrelated_invalid_model(
    multi_model_adapter,
):
    models_path = multi_model_adapter.config.semantic_models_path
    with open(f"{models_path}/broken.yml", "w", encoding="utf-8") as stream:
        stream.write(
            "version: 0.2.0.dev0\n"
            "semantic_model:\n"
            "  - name: broken\n"
            "    datasets:\n"
            "      - name: missing_source\n"
        )

    result = await multi_model_adapter.validate_semantic(
        scope="semantic_model",
        semantic_model_name="finance_budget",
        checks=["profile"],
    )

    assert result.valid


def test_backend_artifacts_are_isolated_by_model(multi_model_adapter, tmp_path):
    backend = MetricFlowBackend(generated_path=str(tmp_path / "generated"))

    commerce_path = backend._write_persistent(
        multi_model_adapter._model("commerce_orders")
    )
    finance_path = backend._write_persistent(
        multi_model_adapter._model("finance_budget")
    )

    assert commerce_path.name == "commerce_orders"
    assert finance_path.name == "finance_budget"
    assert (commerce_path / "semantic_models.yaml").is_file()
    assert (finance_path / "semantic_models.yaml").is_file()


async def test_validate_semantic_passes(adapter):
    result = await adapter.validate_semantic()
    errors = [i for i in result.issues if i.severity == "error"]
    assert result.valid, f"errors: {[e.message for e in errors]}"


async def test_list_metrics_returns_generated_metric(adapter):
    metrics = await adapter.list_metrics()
    names = {m.name for m in metrics}
    assert "order_count" in names


async def test_list_metrics_exposes_osi_structured_metadata(adapter):
    metrics = {m.name: m for m in await adapter.list_metrics()}

    base = metrics["order_count"]
    assert base.path == ["commerce", "orders"]
    assert base.metadata["metric_kind"] == "aggregate"
    assert base.metadata["dataset"] == "orders"
    assert base.metadata["subject_path"] == ["commerce", "orders"]

    mom = metrics["order_count_mom"]
    assert mom.type == "derived"
    assert mom.metadata["metric_kind"] == "derived"
    assert (
        mom.metadata["expr"]
        == "(order_count - order_count_prev) / NULLIF(order_count_prev, 0)"
    )
    assert mom.metadata["offset_window"] == "1 month"
    assert mom.metadata["inputs"] == [
        {"name": "order_count"},
        {
            "name": "order_count",
            "alias": "order_count_prev",
            "offset_window": "1 month",
        },
    ]
    assert mom.metadata["dataset"] == "orders"
    assert "order_channel" in mom.dimensions

    yoy = metrics["order_count_month_yoy"]
    assert yoy.type == "aggregate"
    assert yoy.metadata["period_over_period"] == {
        "time_grain": "month",
        "offset_window": "1 year",
        "calculation": "percent_change",
    }
    assert yoy.metadata["time_dimension"] == "order_date"
    assert "order_channel" in yoy.dimensions

    wow = metrics["order_count_week_wow_delta"]
    assert wow.metadata["period_over_period"] == {
        "time_grain": "week",
        "offset_window": "1 week",
        "calculation": "delta",
    }
    assert wow.metadata["time_dimension"] == "order_date"


async def test_list_metrics_selects_subject_path(adapter):
    metrics = await adapter.list_metrics(path=["commerce"])
    assert {m.name for m in metrics} == {
        "order_count",
        "average_order_amount",
        "running_order_count",
        "moving_3_month_order_count_avg",
        "rolling_order_count_level",
        "moving_window_month_count",
        "running_min_average_order_amount",
        "running_max_average_order_amount",
        "order_count_mom",
        "previous_month_order_count",
        "order_count_month_yoy",
        "order_count_week_wow_delta",
        "running_week_order_count",
    }


def test_offset_derived_metrics_use_current_period_anchor(adapter):
    query_metrics, hidden_anchor_metrics, filter_anchor_metrics = (
        adapter._query_metrics_plan(
            adapter._resolve_query_model(["order_count_mom"]),
            ["order_count_mom"],
        )
    )

    assert query_metrics == ["order_count_mom", "order_count"]
    assert hidden_anchor_metrics == ["order_count"]
    assert filter_anchor_metrics == ["order_count"]


def test_offset_only_metrics_use_referenced_metric_as_anchor(adapter):
    query_metrics, hidden_anchor_metrics, filter_anchor_metrics = (
        adapter._query_metrics_plan(
            adapter._resolve_query_model(["previous_month_order_count"]),
            ["previous_month_order_count"],
        )
    )

    assert query_metrics == ["previous_month_order_count", "order_count"]
    assert hidden_anchor_metrics == ["order_count"]
    assert filter_anchor_metrics == ["order_count"]


def test_period_over_period_metrics_use_generated_base_as_anchor(adapter):
    query_metrics, hidden_anchor_metrics, filter_anchor_metrics = (
        adapter._query_metrics_plan(
            adapter._resolve_query_model(["order_count_month_yoy"]),
            ["order_count_month_yoy"],
        )
    )

    assert query_metrics == [
        "order_count_month_yoy",
        "datus_pop_base_order_count_month_yoy",
    ]
    assert hidden_anchor_metrics == ["datus_pop_base_order_count_month_yoy"]
    assert filter_anchor_metrics == ["datus_pop_base_order_count_month_yoy"]


def test_week_period_over_period_metrics_use_generated_base_as_anchor(adapter):
    query_metrics, hidden_anchor_metrics, filter_anchor_metrics = (
        adapter._query_metrics_plan(
            adapter._resolve_query_model(["order_count_week_wow_delta"]),
            ["order_count_week_wow_delta"],
        )
    )

    assert query_metrics == [
        "order_count_week_wow_delta",
        "datus_pop_base_order_count_week_wow_delta",
    ]
    assert hidden_anchor_metrics == ["datus_pop_base_order_count_week_wow_delta"]
    assert filter_anchor_metrics == ["datus_pop_base_order_count_week_wow_delta"]


def test_offset_anchor_filter_removes_offset_only_rows(adapter):
    result = QueryResult(
        columns=[
            "metric_time__month",
            "customer_segment",
            "order_count_mom",
            "order_count",
        ],
        data=[
            {
                "metric_time__month": "2025-09-01",
                "customer_segment": "enterprise",
                "order_count_mom": None,
                "order_count": 1.0,
            },
            {
                "metric_time__month": "2025-10-01",
                "customer_segment": "enterprise",
                "order_count_mom": None,
                "order_count": None,
            },
        ],
    )

    filtered = adapter._filter_offset_anchor_rows(
        result,
        hidden_anchor_metrics=["order_count"],
        filter_anchor_metrics=["order_count"],
    )

    assert filtered.columns == [
        "metric_time__month",
        "customer_segment",
        "order_count_mom",
    ]
    assert filtered.data == [
        {
            "metric_time__month": "2025-09-01",
            "customer_segment": "enterprise",
            "order_count_mom": None,
        }
    ]
    assert filtered.metadata["hidden_offset_anchor_metrics"] == ["order_count"]
    assert filtered.metadata["offset_anchor_filtered_rows"] == 1


async def test_get_dimensions_includes_declared_dimension(adapter):
    dims = await adapter.get_dimensions("order_count")
    names = {d.name for d in dims}
    assert "order_channel" in names
    assert "order_date" in names


async def test_query_metrics_dry_run_renders_sql(adapter):
    result = await adapter.query_metrics(["order_count"], dry_run=True)
    sql = result.metadata.get("sql", "") or (
        result.data[0]["sql"] if result.data else ""
    )
    assert "COUNT(DISTINCT order_id)" in sql
    assert "fact_orders" in sql


async def test_query_metrics_period_over_period_uses_fixed_metric_contract(adapter):
    executor = _FakeExecutor(
        result=QueryResult(
            columns=[
                "metric_time__month",
                "order_channel",
                "order_count_month_yoy",
                "datus_pop_base_order_count_month_yoy",
            ],
            data=[
                {
                    "metric_time__month": "2025-12-01",
                    "order_channel": "online",
                    "order_count_month_yoy": 0.08,
                    "datus_pop_base_order_count_month_yoy": 100,
                },
                {
                    "metric_time__month": "2026-01-01",
                    "order_channel": "online",
                    "order_count_month_yoy": 0.12,
                    "datus_pop_base_order_count_month_yoy": 120,
                },
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count_month_yoy"],
        dimensions=["order_channel"],
        time_start="2026-01-01",
        time_end="2026-12-31",
    )

    call = executor.calls[0]
    assert call["metrics"] == [
        "order_count_month_yoy",
        "datus_pop_base_order_count_month_yoy",
    ]
    assert call["dimensions"] == ["order_channel", "metric_time__month"]
    assert call["time_granularity"] == "month"
    assert call["time_start"] == "2025-01-01"
    assert result.data == [
        {
            "metric_time__month": "2026-01-01",
            "order_channel": "online",
            "order_count_month_yoy": 0.12,
        }
    ]
    assert result.columns == [
        "metric_time__month",
        "order_channel",
        "order_count_month_yoy",
    ]
    assert result.metadata["period_over_period"] == {
        "order_count_month_yoy": {
            "time_grain": "month",
            "offset_window": "1 year",
            "calculation": "percent_change",
        }
    }
    assert result.metadata["period_over_period_expanded_time_start"] == "2025-01-01"
    assert result.metadata["period_over_period_filtered_rows"] == 1
    assert result.metadata["hidden_offset_anchor_metrics"] == [
        "datus_pop_base_order_count_month_yoy"
    ]


async def test_query_metrics_period_over_period_rejects_conflicting_grain(adapter):
    adapter._backend = _FakeBackend(_FakeExecutor())

    with pytest.raises(ValueError, match="time_grain"):
        await adapter.query_metrics(
            ["order_count_month_yoy"],
            time_granularity="week",
        )


async def test_query_metrics_period_over_period_rejects_conflicting_metric_time_dimension(
    adapter,
):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(ValueError, match="metric_time__day"):
        await adapter.query_metrics(
            ["order_count_month_yoy"],
            dimensions=["metric_time__day"],
        )

    assert executor.calls == []


async def test_query_metrics_period_over_period_rejects_invalid_date_boundaries(
    adapter,
):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(ValueError, match="time_start"):
        await adapter.query_metrics(
            ["order_count_month_yoy"],
            time_start="2026-01-01'; DROP TABLE orders; --",
        )

    with pytest.raises(ValueError, match="time_end"):
        await adapter.query_metrics(
            ["order_count_month_yoy"],
            time_start="2026-01-01",
            time_end="not-a-date",
        )

    assert executor.calls == []


async def test_query_metrics_period_over_period_accepts_plural_multi_count_offset(
    tmp_path,
):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
metrics:
  - name: order_count_two_month_delta
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    period_over_period:
      time_grain: month
      offset_window: "2 months"
      calculation: delta
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(
        result=QueryResult(
            columns=[
                "metric_time__month",
                "order_count_two_month_delta",
                "datus_pop_base_order_count_two_month_delta",
            ],
            data=[
                {
                    "metric_time__month": "2025-11-01",
                    "order_count_two_month_delta": None,
                    "datus_pop_base_order_count_two_month_delta": 10,
                },
                {
                    "metric_time__month": "2026-01-01",
                    "order_count_two_month_delta": 3,
                    "datus_pop_base_order_count_two_month_delta": 13,
                },
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count_two_month_delta"],
        time_start="2026-01-01",
        time_end="2026-01-31",
    )

    assert executor.calls[0]["time_start"] == "2025-11-01"
    assert executor.calls[0]["dimensions"] == ["metric_time__month"]
    assert result.data == [
        {
            "metric_time__month": "2026-01-01",
            "order_count_two_month_delta": 3,
        }
    ]
    assert result.metadata["period_over_period"] == {
        "order_count_two_month_delta": {
            "time_grain": "month",
            "offset_window": "2 months",
            "calculation": "delta",
        }
    }


async def test_query_metrics_period_over_period_uses_week_grain_contract(adapter):
    executor = _FakeExecutor(
        result=QueryResult(
            columns=[
                "metric_time__week",
                "order_channel",
                "order_count_week_wow_delta",
                "datus_pop_base_order_count_week_wow_delta",
            ],
            data=[
                {
                    "metric_time__week": "2026-01-05",
                    "order_channel": "online",
                    "order_count_week_wow_delta": 4,
                    "datus_pop_base_order_count_week_wow_delta": 20,
                },
                {
                    "metric_time__week": "2026-01-12",
                    "order_channel": "online",
                    "order_count_week_wow_delta": -2,
                    "datus_pop_base_order_count_week_wow_delta": 18,
                },
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count_week_wow_delta"],
        dimensions=["order_channel"],
        time_start="2026-01-12",
        time_end="2026-01-31",
    )

    call = executor.calls[0]
    assert call["metrics"] == [
        "order_count_week_wow_delta",
        "datus_pop_base_order_count_week_wow_delta",
    ]
    assert call["dimensions"] == ["order_channel", "metric_time__week"]
    assert call["time_granularity"] == "week"
    assert call["time_start"] == "2026-01-05"
    assert result.columns == [
        "metric_time__week",
        "order_channel",
        "order_count_week_wow_delta",
    ]
    assert result.data == [
        {
            "metric_time__week": "2026-01-12",
            "order_channel": "online",
            "order_count_week_wow_delta": -2,
        }
    ]
    assert result.metadata["period_over_period_filtered_rows"] == 1


async def test_query_metrics_period_over_period_rejects_mixed_fixed_grains(adapter):
    adapter._backend = _FakeBackend(_FakeExecutor())

    with pytest.raises(ValueError, match="different time_grain"):
        await adapter.query_metrics(
            ["order_count_month_yoy", "order_count_week_wow_delta"],
        )


async def test_query_metrics_dimension_preserving_dry_run_uses_policy_sql(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )

    result = await adapter.query_metrics(
        ["order_count"],
        dimensions=["customer_id__customer_name"],
        join_policy="dimension_preserving",
        zero_fill=True,
        dry_run=True,
    )

    sql = result.metadata["sql"]
    assert "LEFT JOIN" in sql
    assert "COALESCE(fact.order_count, 0)" in sql
    assert result.metadata["join_policy"] == "dimension_preserving"


async def test_query_metrics_dimension_preserving_accepts_dimension_expression(
    tmp_path,
):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions:
      - name: signup_month
        expr: "DATE_TRUNC('month', created_at)"
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )

    result = await adapter.query_metrics(
        ["order_count"],
        dimensions=["customer_id__signup_month"],
        join_policy="dimension_preserving",
        zero_fill=True,
        dry_run=True,
    )

    sql = result.metadata["sql"]
    assert "DATE_TRUNC" in sql
    assert "AS signup_month" in sql
    assert "SELECT dim.signup_month AS signup_month" in sql
    assert "LEFT JOIN" in sql


async def test_query_metrics_match_only_drops_unmatched_joined_dimension(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(
        QueryResult(
            columns=["customer_name", "order_count"],
            data=[
                {"customer_name": "Alice", "order_count": 2},
                {"customer_name": None, "order_count": 1},
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count"], dimensions=["customer_id__customer_name"]
    )

    assert result.data == [{"customer_name": "Alice", "order_count": 2}]
    assert result.metadata["join_policy"] == "match_only"
    assert result.metadata["join_policy_filtered_rows"] == 1


async def test_query_metrics_match_only_preserves_zero_filter_metadata(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(
        QueryResult(
            columns=["customer_name", "order_count"],
            data=[{"customer_name": "Alice", "order_count": 2}],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count"], dimensions=["customer_id__customer_name"]
    )

    assert result.data == [{"customer_name": "Alice", "order_count": 2}]
    assert result.metadata["join_policy"] == "match_only"
    assert result.metadata["join_policy_filtered_rows"] == 0


async def test_query_metrics_dimension_preserving_uses_dimension_anchor_sql(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(
        sql_rows=[
            {"customer_name": "Alice", "order_count": 2},
            {"customer_name": "Bob", "order_count": 0},
        ]
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["order_count"],
        dimensions=["customer_id__customer_name"],
        join_policy="dimension_preserving",
        zero_fill=True,
        time_start="2025-01-01",
        time_end="2025-01-31",
        where="order_channel = 'web'",
        order_by=["-customer_id__customer_name"],
    )

    assert result.data == [
        {"customer_name": "Alice", "order_count": 2},
        {"customer_name": "Bob", "order_count": 0},
    ]
    sql = executor.sql_queries[0]
    assert "LEFT JOIN" in sql
    assert "COALESCE(fact.order_count, 0)" in sql
    assert "order_date >= '2025-01-01'" in sql
    assert "order_channel = 'web'" in sql
    assert "ORDER BY customer_name DESC" in sql
    assert result.metadata["join_policy"] == "dimension_preserving"


async def test_query_metrics_dimension_preserving_rejects_unsafe_runtime_sql(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    adapter._backend = _FakeBackend(_FakeExecutor())

    with pytest.raises(ValueError, match="time_start"):
        await adapter.query_metrics(
            ["order_count"],
            dimensions=["customer_id__customer_name"],
            join_policy="dimension_preserving",
            time_start="2025-01-01'; DROP TABLE orders; --",
        )

    with pytest.raises(ValueError, match="order_by column"):
        await adapter.query_metrics(
            ["order_count"],
            dimensions=["customer_id__customer_name"],
            join_policy="dimension_preserving",
            order_by=["customer_name; DROP TABLE orders"],
        )


async def test_query_metrics_dimension_preserving_rejects_mixed_fact_sources(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: refunds
    source: {table: refunds}
    primary_key: refund_id
    time_dimension: {name: refund_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
  - {name: r2c, from: refunds, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: refund_count
    expression: "COUNT(DISTINCT refund_id)"
    dataset: refunds
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(QueryResult(columns=["customer_name"], data=[]))
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(ValueError, match="dimension_preserving"):
        await adapter.query_metrics(
            ["order_count", "refund_count"],
            dimensions=["customer_id__customer_name"],
            join_policy="dimension_preserving",
        )

    assert executor.sql_queries == []
    assert executor.calls == []


async def test_query_metrics_dimension_preserving_falls_back_for_derived_metric(
    tmp_path,
):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: revenue
    expression: "SUM(order_amount)"
    dataset: orders
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: average_order_value
    metric_kind: derived
    expression: "revenue / NULLIF(order_count, 0)"
    inputs: [revenue, order_count]
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(QueryResult(columns=["customer_name"], data=[]))
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(ValueError, match="dimension_preserving"):
        await adapter.query_metrics(
            ["average_order_value"],
            dimensions=["customer_id__customer_name"],
            join_policy="dimension_preserving",
        )

    assert executor.sql_queries == []
    assert executor.calls == []


async def test_query_metrics_dimension_preserving_requires_shared_time_dimension(
    tmp_path,
):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: customer_name, expr: customer_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: shipped_order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: ship_date
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )
    executor = _FakeExecutor(QueryResult(columns=["customer_name"], data=[]))
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(ValueError, match="dimension_preserving"):
        await adapter.query_metrics(
            ["order_count", "shipped_order_count"],
            dimensions=["customer_id__customer_name"],
            join_policy="dimension_preserving",
            time_start="2025-01-01",
        )

    assert executor.sql_queries == []
    assert executor.calls == []


async def test_query_metrics_postprocesses_window_metrics(adapter):
    executor = _FakeExecutor(
        QueryResult(
            columns=["metric_time__month", "order_count", "average_order_amount"],
            data=[
                {
                    "metric_time__month": "2025-01-01",
                    "order_count": 10,
                    "average_order_amount": 50,
                },
                {
                    "metric_time__month": "2025-02-01",
                    "order_count": 20,
                    "average_order_amount": 70,
                },
                {
                    "metric_time__month": "2025-03-01",
                    "order_count": 30,
                    "average_order_amount": 60,
                },
                {
                    "metric_time__month": "2025-04-01",
                    "order_count": 40,
                    "average_order_amount": 90,
                },
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        [
            "order_count",
            "running_order_count",
            "moving_3_month_order_count_avg",
            "rolling_order_count_level",
            "moving_window_month_count",
            "average_order_amount",
            "running_min_average_order_amount",
            "running_max_average_order_amount",
        ],
        dimensions=["metric_time__month"],
        time_granularity="month",
    )

    assert executor.calls[0]["metrics"] == ["order_count", "average_order_amount"]
    assert result.columns == [
        "metric_time__month",
        "order_count",
        "average_order_amount",
        "running_order_count",
        "moving_3_month_order_count_avg",
        "rolling_order_count_level",
        "moving_window_month_count",
        "running_min_average_order_amount",
        "running_max_average_order_amount",
    ]
    assert [row["running_order_count"] for row in result.data] == [10, 30, 60, 100]
    assert [row["moving_3_month_order_count_avg"] for row in result.data] == [
        10,
        15,
        20,
        30,
    ]
    assert [row["rolling_order_count_level"] for row in result.data] == [10, 15, 20, 30]
    assert [row["moving_window_month_count"] for row in result.data] == [1, 2, 3, 3]
    assert [row["running_min_average_order_amount"] for row in result.data] == [
        50,
        50,
        50,
        50,
    ]
    assert [row["running_max_average_order_amount"] for row in result.data] == [
        50,
        70,
        70,
        90,
    ]


async def test_query_metrics_window_postprocessing_preserves_backend_row_order(adapter):
    executor = _FakeExecutor(
        QueryResult(
            columns=["metric_time__month", "order_count"],
            data=[
                {"metric_time__month": "2025-03-01", "order_count": 30},
                {"metric_time__month": "2025-01-01", "order_count": 10},
                {"metric_time__month": "2025-02-01", "order_count": 20},
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["running_order_count"],
        dimensions=["metric_time__month"],
        time_granularity="month",
        order_by=["-metric_time__month"],
    )

    assert [row["metric_time__month"] for row in result.data] == [
        "2025-03-01",
        "2025-01-01",
        "2025-02-01",
    ]
    assert [row["running_order_count"] for row in result.data] == [60, 10, 30]


async def test_query_metrics_row_count_window_does_not_call_executor_with_empty_metrics(
    adapter,
):
    executor = _FakeExecutor(
        QueryResult(
            columns=["metric_time__month", "moving_window_month_count"],
            data=[
                {"metric_time__month": "2025-01-01", "moving_window_month_count": 1},
                {"metric_time__month": "2025-02-01", "moving_window_month_count": 1},
                {"metric_time__month": "2025-03-01", "moving_window_month_count": 1},
            ],
        )
    )
    adapter._backend = _FakeBackend(executor)

    result = await adapter.query_metrics(
        ["moving_window_month_count"],
        dimensions=["metric_time__month"],
        time_granularity="month",
    )

    assert executor.calls[0]["metrics"] == ["moving_window_month_count"]
    assert [row["moving_window_month_count"] for row in result.data] == [1, 2, 3]


async def test_validate_semantic_warns_for_normalized_dataset_alias(tmp_path):
    (tmp_path / "alias.yml").write_text(
        _core_yaml(
            """
datasets:
  - name: orders_alias
    source: {table: fact_orders}
    primary_key: order_id
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders_alias
"""
        )
    )
    (tmp_path / "canonical.yml").write_text(
        _core_yaml(
            """
datasets:
  - name: fact_orders
    source: {table: fact_orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="starrocks")
    )

    result = await adapter.validate_semantic()

    assert result.valid
    warnings = [i.message for i in result.issues if i.severity == "warning"]
    assert any(
        "Collapsed duplicate dataset `orders_alias`" in message for message in warnings
    )
    metrics = await adapter.list_metrics()
    assert metrics[0].metadata["dataset"] == "fact_orders"


async def test_get_dimensions_includes_joined_dimensions(tmp_path):
    (tmp_path / "model.yaml").write_text(
        _core_yaml(
            """
semantic_model:
  name: shop
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
  - name: customers
    source: {table: customers}
    primary_key: customer_id
    dimensions: [{name: region_id, expr: region_id}]
  - name: regions
    source: {table: regions}
    primary_key: region_id
    dimensions: [{name: region_name, expr: region_name}]
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
  - {name: c2r, from: customers, to: regions, from_columns: [region_id], to_columns: [region_id]}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
        )
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )

    dims = await adapter.get_dimensions("order_count")
    names = {d.name for d in dims}
    assert "order_date" in names
    assert "customer_id__region_id" in names
    assert "customer_id__region_id__region_name" in names

    metrics = await adapter.list_metrics()
    assert "customer_id__region_id__region_name" in metrics[0].dimensions


async def test_get_dimensions_excludes_plain_measure_source_fields(tmp_path):
    # A field without a `dimension:` block is a row-level measure source per
    # OSI core; it must not be listed as a queryable dimension.
    (tmp_path / "model.yaml").write_text(
        """
version: 0.2.0.dev0
semantic_model:
  - name: lending
    datasets:
      - name: loan_quality
        source: dm.loan_quality
        fields:
          - name: snapshot_date
            expression:
              dialects: [{dialect: ANSI_SQL, expression: snapshot_date}]
            dimension: {is_time: true}
            custom_extensions:
              - vendor_name: DATUS
                data: '{"time_granularity": "month"}'
          - name: branch_no
            expression:
              dialects: [{dialect: ANSI_SQL, expression: branch_no}]
            dimension: {}
          - name: loan_balance
            expression:
              dialects: [{dialect: ANSI_SQL, expression: loan_balance}]
            description: "aggregation-only balance column"
    metrics:
      - name: loan_balance_total
        description: "Total loan balance"
        expression:
          dialects: [{dialect: ANSI_SQL, expression: "SUM(loan_quality.loan_balance)"}]
        custom_extensions:
          - vendor_name: DATUS
            data: '{"time_dimension": "snapshot_date"}'
"""
    )
    adapter = DatusOSIAdapter(
        DatusOSIConfig(semantic_models_path=str(tmp_path), datasource="duckdb")
    )

    dims = await adapter.get_dimensions("loan_balance_total")
    names = {d.name for d in dims}
    assert "branch_no" in names
    assert "snapshot_date" in names
    assert "loan_balance" not in names

    metrics = await adapter.list_metrics()
    assert "loan_balance" not in metrics[0].dimensions


def _injected_dimensions(executor):
    """metric_time dimensions the adapter passed to the backend executor."""
    assert executor.calls, "expected the executor to be invoked"
    return [
        d for d in executor.calls[0]["dimensions"] if str(d).startswith("metric_time")
    ]


async def test_query_metrics_injects_metric_time_for_cumulative(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(["running_order_count"])

    # grain_to_date: month -> group by metric_time__month, caller supplied none
    assert _injected_dimensions(executor) == ["metric_time__month"]


async def test_query_metrics_injects_metric_time_for_offset_derived(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(["previous_month_order_count"])

    # derived metric with an offset_window "1 month" input requires metric_time
    assert "metric_time__month" in executor.calls[0]["dimensions"]


async def test_query_metrics_injects_metric_time_for_window(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(["moving_3_month_order_count_avg"])

    # window "3 months" is post-processed over the monthly base metric
    assert _injected_dimensions(executor) == ["metric_time__month"]


async def test_query_metrics_no_time_injection_for_plain_aggregate(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(["order_count"])

    assert _injected_dimensions(executor) == []


async def test_query_metrics_time_grouping_is_idempotent(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(
        ["running_order_count"], dimensions=["metric_time__day"]
    )

    # caller's explicit metric_time grain is respected, not overridden or doubled
    assert _injected_dimensions(executor) == ["metric_time__day"]


async def test_query_metrics_uses_single_time_group_for_compatible_metrics(adapter):
    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    await adapter.query_metrics(["previous_month_order_count", "running_order_count"])

    assert _injected_dimensions(executor) == ["metric_time__month"]


async def test_query_metrics_rejects_conflicting_required_time_grains(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    executor = _FakeExecutor()
    adapter._backend = _FakeBackend(executor)

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["running_order_count", "running_week_order_count"])

    payload = excinfo.value.payload
    assert payload.code == "metric_time_grain_conflict"
    assert payload.metrics == ["running_order_count", "running_week_order_count"]
    assert not executor.calls


class InvalidQueryException(Exception):
    """Stand-in matching MetricFlow's InvalidQueryException by class name."""


class _RaisingExecutor:
    def __init__(self, exc):
        self._exc = exc
        self.calls = []

    async def query_metrics(self, metrics, **kwargs):
        self.calls.append({"metrics": list(metrics), **kwargs})
        raise self._exc


async def test_query_metrics_maps_cumulative_rejection_to_structured(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    exc = InvalidQueryException(
        "The query includes a cumulative metric 'running_order_count' that does not "
        "accumulate over all-time, but the group-by items do not include 'metric_time'."
    )
    adapter._backend = _FakeBackend(_RaisingExecutor(exc))

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["order_count"])

    payload = excinfo.value.payload
    assert payload.error_type == "semantic_validation_error"
    assert payload.code == "cumulative_requires_metric_time"
    assert "metric_time" in payload.required_dimensions
    assert payload.metrics == ["order_count"]


async def test_query_metrics_maps_time_grain_required(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    exc = InvalidQueryException(
        "For querying cumulative metric 'moving_3_month_avg', the granularity of "
        "'metric_time__month' must be DAY"
    )
    adapter._backend = _FakeBackend(_RaisingExecutor(exc))

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["order_count"])

    payload = excinfo.value.payload
    assert payload.code == "time_grain_required"
    assert payload.required_time_granularity == "day"
    assert payload.required_dimensions == ["metric_time__day"]
    assert payload.suggested_retry == {
        "dimensions": ["metric_time__day"],
        "time_granularity": "day",
    }


async def test_query_metrics_unknown_validation_error_stays_structured(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    exc = InvalidQueryException("some brand new validation rule not yet mapped")
    adapter._backend = _FakeBackend(_RaisingExecutor(exc))

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["order_count"])

    payload = excinfo.value.payload
    assert payload.code == "validation_error"
    assert "brand new validation rule" in payload.message


async def test_query_metrics_infra_error_propagates_unwrapped(adapter):
    adapter._backend = _FakeBackend(_RaisingExecutor(RuntimeError("connection lost")))

    # non-validation failures must not be masked as validation errors
    with pytest.raises(RuntimeError):
        await adapter.query_metrics(["order_count"])


class RequestTimeGranularityException(Exception):
    """Stand-in matching MetricFlow's RequestTimeGranularityException by class name."""


class UnableToSatisfyQueryError(Exception):
    """Stand-in matching MetricFlow's UnableToSatisfyQueryError by class name."""


class ExecutionException(Exception):
    """Stand-in matching MetricFlow's runtime ExecutionException by class name."""


async def test_query_metrics_classifies_granularity_exception(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    # MetricFlow raises RequestTimeGranularityException (not InvalidQuery*) for
    # cumulative-metric grain rejections; it must still map to structured guidance.
    exc = RequestTimeGranularityException(
        "For querying cumulative metric 'running_activity_count', the granularity of "
        "'metric_time__month' must be DAY"
    )
    adapter._backend = _FakeBackend(_RaisingExecutor(exc))

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["order_count"])

    payload = excinfo.value.payload
    assert payload.code == "time_grain_required"
    assert payload.required_time_granularity == "day"
    assert payload.required_dimensions == ["metric_time__day"]


async def test_query_metrics_classifies_unsatisfiable_query_exception(adapter):
    from datus_semantic_osi.errors import SemanticValidationException

    exc = UnableToSatisfyQueryError("Recipe not found for linkable specs")
    adapter._backend = _FakeBackend(_RaisingExecutor(exc))

    with pytest.raises(SemanticValidationException) as excinfo:
        await adapter.query_metrics(["order_count"])

    assert excinfo.value.payload.code == "validation_error"
    assert "Recipe not found" in excinfo.value.payload.message


async def test_query_metrics_execution_exception_propagates_unwrapped(adapter):
    # ExecutionException is a runtime/infra family, not a validation rejection.
    adapter._backend = _FakeBackend(_RaisingExecutor(ExecutionException("SQL timeout")))

    with pytest.raises(ExecutionException):
        await adapter.query_metrics(["order_count"])

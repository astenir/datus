# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for IR -> MetricFlow YAML lowering (legacy data_source dialect)."""

import pytest

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import DatasetIR, IdentifierIR, RelationshipIR, SemanticModelIR
from datus_semantic_osi.metricflow_backend import MetricFlowArtifact, lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

OSI_YAML = """
semantic_model:
  name: order_model
datasets:
  - name: completed_orders
    source:
      query: "SELECT * FROM orders WHERE status = 'completed'"
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
    dimensions:
      - name: status
        expr: status
metrics:
  - name: completed_order_count
    description: "Completed order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: completed_orders
    time_dimension: order_date
"""


def _lower():
    return lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))


def test_query_backed_dataset_keeps_authored_where_clause():
    art = _lower()
    ds = art.data_source_docs[0]["data_source"]
    assert ds["name"] == "completed_orders"
    assert "sql_query" in ds
    assert "orders" in ds["sql_query"]
    assert "status = 'completed'" in ds["sql_query"]
    assert ds["owners"]


def test_query_backed_dataset_keeps_authored_query():
    osi = """
semantic_model:
  name: query_model
datasets:
  - name: regional_orders
    source:
      query: |
        SELECT region, SUM(amount) AS amount
        FROM orders
        WHERE region = 'east'
        GROUP BY region
    dimensions:
      - name: region
        expr: region
metrics:
  - name: total_amount
    expression: "SUM(amount)"
    dataset: regional_orders
"""
    art = lower_to_metricflow(compile_document(parse_osi(osi)))
    sql_query = art.data_source_docs[0]["data_source"]["sql_query"]
    assert sql_query.startswith("SELECT region, SUM(amount) AS amount")
    assert "WHERE region = 'east'" in sql_query
    assert "GROUP BY region" in sql_query


def test_data_source_has_primary_time_dimension_and_measure():
    ds = _lower().data_source_docs[0]["data_source"]
    time_dims = [d for d in ds["dimensions"] if d["type"] == "time"]
    assert time_dims and time_dims[0]["type_params"]["is_primary"] is True
    measures = {m["name"]: m for m in ds["measures"]}
    name = "completed_orders_order_id_count_distinct"
    assert measures[name]["agg"] == "count_distinct"
    assert measures[name]["expr"] == "order_id"


def test_aggregate_metric_lowers_to_measure_proxy():
    metric = _lower().metric_docs[0]["metric"]
    assert metric["name"] == "completed_order_count"
    assert metric["type"] == "measure_proxy"
    assert metric["type_params"]["measures"] == [
        "completed_orders_order_id_count_distinct"
    ]


def test_dimension_colliding_with_identifier_is_dropped():
    # A column declared as both primary_key and a dimension must not be lowered
    # as a MetricFlow dimension (identifier/dimension name collision is invalid).
    osi = """
semantic_model:
  name: shop
datasets:
  - name: orders
    source:
      table: orders
    primary_key: order_id
    dimensions:
      - name: order_id
        expr: order_id
      - name: status
        expr: status
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""
    art = lower_to_metricflow(compile_document(parse_osi(osi)))
    ds = art.data_source_docs[0]["data_source"]
    dim_names = {d["name"] for d in ds.get("dimensions", [])}
    id_names = {i["name"] for i in ds.get("identifiers", [])}
    assert "order_id" in id_names
    assert "order_id" not in dim_names
    assert "status" in dim_names


def test_artifact_renders_multidoc_yaml():
    art = _lower()
    sm_yaml = art.semantic_models_yaml()
    assert "data_source:" in sm_yaml
    metrics_yaml = art.metrics_yaml()
    assert "metric:" in metrics_yaml


def test_artifact_write_removes_stale_metrics_yaml(tmp_path):
    stale_metrics = tmp_path / "metrics.yaml"
    stale_metrics.write_text("metric:\n  name: stale\n", encoding="utf-8")

    artifact = MetricFlowArtifact(
        data_source_docs=[
            {"data_source": {"name": "empty_metrics", "sql_query": "SELECT 1"}}
        ],
        metric_docs=[],
    )
    written = artifact.write(tmp_path)

    assert "metrics" not in written
    assert not stale_metrics.exists()


def test_duplicate_relationship_foreign_identifier_name_is_rejected():
    model = SemanticModelIR(
        datasets=[
            DatasetIR(name="fact", sql_table="fact_orders"),
            DatasetIR(
                name="buyers",
                sql_table="buyers",
                identifiers=[
                    IdentifierIR(
                        name="customer_id", type="primary", expr="customer_id"
                    )
                ],
            ),
            DatasetIR(
                name="sellers",
                sql_table="sellers",
                identifiers=[
                    IdentifierIR(
                        name="customer_id", type="primary", expr="customer_id"
                    )
                ],
            ),
        ],
        relationships=[
            RelationshipIR(
                name="fact_to_buyers",
                type="many_to_one",
                from_dataset="fact",
                from_identifier="buyer_id",
                to_dataset="buyers",
                to_identifier="customer_id",
            ),
            RelationshipIR(
                name="fact_to_sellers",
                type="many_to_one",
                from_dataset="fact",
                from_identifier="seller_id",
                to_dataset="sellers",
                to_identifier="customer_id",
            ),
        ],
    )

    with pytest.raises(OSIValidationError, match="duplicate foreign identifier"):
        lower_to_metricflow(model)

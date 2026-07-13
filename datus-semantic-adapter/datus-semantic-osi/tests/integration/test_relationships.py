# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Many-to-one relationships lower to MetricFlow joins and validate."""

import pytest

pytest.importorskip("metricflow")

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.ir import RelationshipIR
from datus_semantic_osi.metricflow_backend import lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

OSI_YAML = """
semantic_model:
  name: shop
datasets:
  - name: customers
    source:
      table: customers
    primary_key: customer_id
    dimensions:
      - name: country
        expr: country
  - name: orders
    source:
      table: orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
relationships:
  - name: order_to_customer
    from: orders
    to: customers
    from_columns: [customer_id]
    to_columns: [customer_id]
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
"""


def test_relationship_compiles_to_ir():
    model = compile_document(parse_osi(OSI_YAML))
    assert len(model.relationships) == 1
    rel = model.relationships[0]
    assert isinstance(rel, RelationshipIR)
    assert rel.from_dataset == "orders"
    assert rel.to_dataset == "customers"


def test_relationship_adds_foreign_identifier_on_from_dataset():
    art = lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))
    sources = {d["data_source"]["name"]: d["data_source"] for d in art.data_source_docs}
    orders_ids = {i["name"]: i for i in sources["orders"].get("identifiers", [])}
    # a foreign identifier named after the customers primary key links the two
    assert "customer_id" in orders_ids
    assert orders_ids["customer_id"]["type"] == "foreign"


def test_joined_model_validates_and_query_groups_by_joined_dimension(tmp_path):
    art = lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))
    art.write(tmp_path)

    from metricflow.api.metricflow_client import MetricFlowClient
    from metricflow.model.model_validator import ModelValidator
    from metricflow.model.parsing.dir_to_model import (
        parse_directory_of_yaml_files_to_model,
    )
    from metricflow.sql_clients.duckdb import DuckDbSqlClient

    build = parse_directory_of_yaml_files_to_model(str(tmp_path))
    assert [str(e) for e in build.issues.errors] == []
    semantic = ModelValidator().validate_model(build.model)
    assert [str(e) for e in semantic.issues.errors] == []

    client = MetricFlowClient(
        sql_client=DuckDbSqlClient(),
        user_configured_model=build.model,
        system_schema="main",
    )
    sql = client.explain(
        metrics=["order_count"], dimensions=["customer_id__country"]
    ).rendered_sql_without_descriptions.sql_query
    assert "JOIN" in sql.upper()

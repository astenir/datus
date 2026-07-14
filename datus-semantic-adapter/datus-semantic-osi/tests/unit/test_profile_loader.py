import pytest

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.profile import (
    load_osi_path,
    parse_osi,
    parse_osi_profile,
    to_core_schema_document,
)


DATASET_DOC = """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        primary_key: [order_id]
        fields:
          - name: order_date
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: order_date
            dimension: {is_time: true}
            custom_extensions:
              - vendor_name: DATUS
                data: '{"type":"time","time_granularity":"day"}'
          - name: customer_segment
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: customer_segment
            dimension: {is_time: false}
            description: "Customer segment"
"""


def test_load_osi_path_recurses_metric_subdirectories(tmp_path):
    (tmp_path / "model.yml").write_text(DATASET_DOC, encoding="utf-8")
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    (metrics_dir / "orders_metrics.yml").write_text(
        DATASET_DOC
        + """
    metrics:
      - name: order_count
        description: "Number of orders"
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT order_id)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders","time_dimension":"order_date"}'
      - name: customer_count
        description: "Number of customer segments"
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT customer_segment)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders","time_dimension":"order_date"}'
""",
        encoding="utf-8",
    )

    doc = load_osi_path(tmp_path)

    assert [dataset.name for dataset in doc.datasets] == ["orders"]
    assert [metric.name for metric in doc.metrics] == ["order_count", "customer_count"]
    assert doc.datasets[0].dimensions[0].description == "Customer segment"


def test_parse_osi_accepts_core_relationship_shape():
    doc = parse_osi(
        """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        primary_key: [order_id]
      - name: customers
        source: customers
        primary_key: [customer_id]
    relationships:
      - name: orders_to_customers
        from: orders
        to: customers
        from_columns: [customer_id]
        to_columns: [customer_id]
    metrics:
      - name: order_count
        description: "Number of orders"
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT order_id)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders"}'
"""
    )

    rel = doc.relationships[0]
    assert rel.from_dataset == "orders"
    assert rel.to_dataset == "customers"
    assert rel.from_identifier == "customer_id"
    assert rel.to_identifier == "customer_id"

    model = compile_document(doc)
    assert model.relationships[0].from_dataset == "orders"
    assert model.relationships[0].from_identifier == "customer_id"


def test_parse_osi_preserves_dataset_ai_context():
    doc = parse_osi(
        """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        description: "Orders dataset"
        ai_context:
          instructions: "Use this dataset for order-level analytics."
          synonyms: ["purchases"]
        primary_key: [order_id]
"""
    )

    assert doc.datasets[0].description == "Orders dataset"
    assert doc.datasets[0].ai_context == {
        "instructions": "Use this dataset for order-level analytics.",
        "synonyms": ["purchases"],
    }
    core = to_core_schema_document(doc)
    dataset = core["semantic_model"][0]["datasets"][0]
    assert (
        dataset["ai_context"]["instructions"]
        == "Use this dataset for order-level analytics."
    )


def test_parse_osi_preserves_metric_ai_context():
    doc = parse_osi(
        """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        primary_key: [order_id]
    metrics:
      - name: order_count
        description: "Number of orders"
        ai_context:
          instructions: "Use for order volume questions."
          synonyms: ["orders"]
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT order_id)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders"}'
"""
    )

    assert doc.metrics[0].ai_context == {
        "instructions": "Use for order volume questions.",
        "synonyms": ["orders"],
    }
    core = to_core_schema_document(doc)
    metric = core["semantic_model"][0]["metrics"][0]
    assert metric["ai_context"]["instructions"] == "Use for order volume questions."


def test_parse_osi_rejects_datus_filter_hint():
    with pytest.raises(Exception, match="not an OSI authoring field"):
        parse_osi(
            """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        primary_key: [order_id]
    metrics:
      - name: paid_order_count
        description: "Paid order count"
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT order_id)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders","filters":[{"expression":"status = ''paid''"}]}'
"""
        )


def test_primary_time_dimension_preserves_expression():
    doc = parse_osi(
        """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        primary_key: [order_id]
        fields:
          - name: order_month
            expression:
              dialects:
                - dialect: ANSI_SQL
                  expression: "DATE_TRUNC('month', order_date)"
            dimension: {is_time: true}
            custom_extensions:
              - vendor_name: DATUS
                data: '{"time_granularity":"month"}'
    metrics:
      - name: order_count
        expression:
          dialects:
            - dialect: ANSI_SQL
              expression: "COUNT(DISTINCT order_id)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"orders","time_dimension":"order_month"}'
"""
    )

    time_dimension = doc.datasets[0].time_dimension
    assert time_dimension is not None
    assert time_dimension.expr == "DATE_TRUNC('month', order_date)"
    model = compile_document(doc)
    primary_time = next(
        field for field in model.datasets[0].fields if field.is_primary_time
    )
    assert primary_time.expr == "DATE_TRUNC('month', order_date)"

    core_doc = to_core_schema_document(doc)
    field = core_doc["semantic_model"][0]["datasets"][0]["fields"][0]
    assert (
        field["expression"]["dialects"][0]["expression"]
        == "DATE_TRUNC('month', order_date)"
    )


def test_parse_osi_rejects_relationships_inside_dataset():
    with pytest.raises(Exception, match="OSI core schema validation failed"):
        parse_osi(
            """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
        relationships:
          - {from: orders, to: customers}
"""
        )


def test_parse_osi_rejects_non_core_relationship_fields():
    with pytest.raises(Exception, match="OSI core schema validation failed"):
        parse_osi(
            """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: orders
        source: orders
      - name: customers
        source: customers
    relationships:
      - name: orders_to_customers
        from: orders
        to: customers
        join_on: orders.customer_id = customers.customer_id
"""
        )


def test_parse_osi_rejects_composite_relationship_columns_for_now():
    with pytest.raises(Exception, match="exactly one column"):
        parse_osi(
            """
version: 0.2.0.dev0
semantic_model:
  - name: shop
    datasets:
      - name: order_lines
        source: order_lines
      - name: orders
        source: orders
    relationships:
      - name: order_lines_to_orders
        from: order_lines
        to: orders
        from_columns: [order_id, tenant_id]
        to_columns: [order_id, tenant_id]
"""
        )


def test_parse_osi_rejects_legacy_profile_by_default():
    with pytest.raises(Exception, match="must conform to OSI core schema"):
        parse_osi("semantic_model: {name: shop}\ndatasets: []\n")


def test_legacy_profile_parser_is_explicit():
    doc = parse_osi_profile(
        "semantic_model: {name: shop}\n"
        "datasets: [{name: orders, source: {table: orders}}]\n"
    )
    assert doc.name == "shop"
    assert doc.datasets[0].source.table == "orders"

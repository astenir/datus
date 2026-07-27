# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""OSI file-level metric authoring."""

import textwrap

import pytest
import yaml

from datus_semantic_osi.authoring import OSIMetricAuthor, _datus_hints
from datus_semantic_osi.errors import OSIValidationError

SAMPLE = textwrap.dedent(
    """\
    version: 0.2.0.dev0
    semantic_model:
      - name: jeff_shop_live
        datasets:
          - name: raw_orders
            source: jeff_shop.raw_orders
            primary_key: [id]
            fields:
              - name: order_total
                expression:
                  dialects:
                    - dialect: STARROCKS
                      expression: order_total
        metrics:
          - name: daily_order_count
            description: "Daily order count."
            expression:
              dialects:
                - dialect: STARROCKS
                  expression: "COUNT(DISTINCT id)"
            custom_extensions:
              - vendor_name: DATUS
                data: '{"dataset":"raw_orders","subject_path":["operations","daily"]}'
    """
)


@pytest.fixture
def root(tmp_path):
    model_dir = tmp_path / "jeff_shop_live"
    model_dir.mkdir()
    (model_dir / "jeff_shop_live.yml").write_text(SAMPLE)
    return str(tmp_path)


def test_read_returns_osi_metric_node(root):
    src = OSIMetricAuthor(root).read("daily_order_count")
    assert src.format == "osi"
    assert src.semantic_model == "jeff_shop_live"
    node = yaml.safe_load(src.text)
    # OSI-native shape preserved (dialect expression + custom extensions), not MetricFlow.
    assert node["expression"]["dialects"][0]["dialect"] == "STARROCKS"
    assert "custom_extensions" in node


def test_read_missing_metric_raises(root):
    with pytest.raises(OSIValidationError):
        OSIMetricAuthor(root).read("nope")


def test_edit_preserves_structure_and_sets_subject_path(root):
    author = OSIMetricAuthor(root)
    src = author.read("daily_order_count")
    edited = src.text.replace("Daily order count.", "Edited.")
    res = author.write("daily_order_count", edited, subject_path=["ops", "vol"])
    assert res.created is False
    reread = yaml.safe_load(author.read("daily_order_count").text)
    assert reread["description"] == "Edited."
    assert _datus_hints(reread)["subject_path"] == ["ops", "vol"]
    # Sibling dataset survived the round-trip.
    docs = list(yaml.safe_load_all(open(res.file_path).read()))
    assert docs[0]["semantic_model"][0]["datasets"][0]["name"] == "raw_orders"


def test_create_attaches_to_model_owning_dataset(root):
    author = OSIMetricAuthor(root)
    new_metric = textwrap.dedent(
        """\
        name: gross_revenue
        description: "revenue"
        expression:
          dialects:
            - dialect: STARROCKS
              expression: "SUM(order_total)"
        custom_extensions:
          - vendor_name: DATUS
            data: '{"dataset":"raw_orders"}'
        """
    )
    res = author.write(
        "gross_revenue", new_metric, subject_path=["revenue"], create=True
    )
    assert res.created is True and res.semantic_model == "jeff_shop_live"
    names = [
        m["name"]
        for m in yaml.safe_load(open(res.file_path).read())["semantic_model"][0][
            "metrics"
        ]
    ]
    assert set(names) == {"daily_order_count", "gross_revenue"}


def test_create_existing_metric_raises(root):
    author = OSIMetricAuthor(root)
    src = author.read("daily_order_count")
    with pytest.raises(OSIValidationError):
        author.write("daily_order_count", src.text, create=True)


def test_edit_missing_metric_raises(root):
    with pytest.raises(OSIValidationError):
        OSIMetricAuthor(root).write("ghost", "name: ghost\n", create=False)


def test_delete_removes_metric_keeps_model(root):
    author = OSIMetricAuthor(root)
    res = author.delete("daily_order_count")
    assert res.deleted is True
    doc = yaml.safe_load(open(res.file_path).read())
    assert doc["semantic_model"][0]["metrics"] == []
    assert doc["semantic_model"][0]["datasets"][0]["name"] == "raw_orders"


def test_validate_reports_success(root):
    author = OSIMetricAuthor(root)
    result = author.validate(
        author.read("daily_order_count").text, metric_name="daily_order_count"
    )
    assert result.valid is True


def test_validate_rejects_bad_yaml(root):
    result = OSIMetricAuthor(root).validate("::: not yaml :::")
    assert result.valid is False


def test_write_tolerates_metricflow_wrapper(root):
    author = OSIMetricAuthor(root)
    src = author.read("daily_order_count")
    wrapped = "metric:\n" + textwrap.indent(src.text, "  ")
    res = author.write("daily_order_count", wrapped)
    assert res.name == "daily_order_count"


def test_edit_preserves_file_permissions(root):
    import os
    import stat

    author = OSIMetricAuthor(root)
    target = os.path.join(root, "jeff_shop_live", "jeff_shop_live.yml")
    os.chmod(target, 0o644)
    src = author.read("daily_order_count")
    author.write("daily_order_count", src.text)
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o644

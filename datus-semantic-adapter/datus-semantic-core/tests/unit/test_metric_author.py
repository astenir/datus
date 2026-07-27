# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Shared file-level MetricAuthor (OSI-format) with the default validator."""

import textwrap

import pytest
import yaml

from datus_semantic_core.metric_author import (
    MetricAuthor,
    MetricAuthoringError,
    _datus_hints,
)

SAMPLE = textwrap.dedent(
    """\
    version: 0.2.0.dev0
    semantic_model:
      - name: jeff_shop_live
        datasets:
          - name: raw_orders
            source: jeff_shop.raw_orders
            primary_key: [id]
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


def test_read_returns_osi_node(root):
    src = MetricAuthor(root).read("daily_order_count")
    assert src.format == "osi"
    assert src.semantic_model == "jeff_shop_live"
    node = yaml.safe_load(src.text)
    assert node["expression"]["dialects"][0]["dialect"] == "STARROCKS"


def test_read_missing_raises_metric_authoring_error(root):
    with pytest.raises(MetricAuthoringError):
        MetricAuthor(root).read("nope")


def test_edit_preserves_structure_and_subject_path(root):
    author = MetricAuthor(root)
    src = author.read("daily_order_count")
    edited = src.text.replace("Daily order count.", "Edited.")
    author.write("daily_order_count", edited, subject_path=["ops", "vol"])
    node = yaml.safe_load(author.read("daily_order_count").text)
    assert node["description"] == "Edited."
    assert _datus_hints(node)["subject_path"] == ["ops", "vol"]


def test_create_attaches_to_model_owning_dataset(root):
    author = MetricAuthor(root)
    new_metric = (
        "name: gross_revenue\n"
        "expression:\n  dialects:\n    - dialect: STARROCKS\n      expression: SUM(order_total)\n"
        'custom_extensions:\n  - vendor_name: DATUS\n    data: \'{"dataset":"raw_orders"}\'\n'
    )
    res = author.write("gross_revenue", new_metric, create=True)
    assert res.created is True and res.semantic_model == "jeff_shop_live"


def test_default_validator_rejects_metric_without_name(root):
    # A structurally invalid document (metric missing name) fails the default
    # validator instead of being written.
    author = MetricAuthor(root)
    result = author.validate("description: no name here\n")
    assert result.valid is False


def test_default_validator_accepts_good_metric(root):
    author = MetricAuthor(root)
    src = author.read("daily_order_count")
    assert author.validate(src.text, metric_name="daily_order_count").valid is True


def test_validate_rejects_bad_yaml(root):
    assert MetricAuthor(root).validate("::: not yaml :::").valid is False


def test_custom_validator_is_invoked(root):
    calls = []

    def strict(doc):
        calls.append(doc)
        raise MetricAuthoringError("nope from custom validator")

    author = MetricAuthor(root, validate_document=strict)
    result = author.validate(author.read("daily_order_count").text)
    assert result.valid is False
    assert calls  # the injected validator ran


def test_file_root_pins_to_one_model_ignoring_siblings(tmp_path):
    # A file root must not discover metrics in sibling files in the same dir.
    (tmp_path / "model_a.yml").write_text(SAMPLE)
    (tmp_path / "model_b.yml").write_text(
        SAMPLE.replace("jeff_shop_live", "other_model").replace(
            "daily_order_count", "sibling_metric"
        )
    )
    author = MetricAuthor(str(tmp_path / "model_a.yml"))
    assert author.read("daily_order_count").name == "daily_order_count"
    with pytest.raises(MetricAuthoringError):
        author.read("sibling_metric")  # lives only in the sibling file

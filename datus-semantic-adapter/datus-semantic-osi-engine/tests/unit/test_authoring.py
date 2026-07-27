# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""osi_engine reuses the OSI file authoring layer verbatim.

Authoring only touches the YAML files (never the Rust binding), so these run
against the fake binding like the rest of the unit suite.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

MODEL = textwrap.dedent(
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
def osi_adapter(tmp_path, make_adapter):
    model_path = tmp_path / "jeff_shop_live.yml"
    model_path.write_text(MODEL)
    return make_adapter(semantic_model_path=str(model_path)), model_path


def test_read_returns_osi_native_yaml(osi_adapter):
    adapter, _ = osi_adapter
    src = adapter.read_metric_source("daily_order_count")
    assert src.format == "osi"
    assert src.semantic_model == "jeff_shop_live"
    node = yaml.safe_load(src.text)
    assert node["expression"]["dialects"][0]["dialect"] == "STARROCKS"
    assert "type" not in node and "locked_metadata" not in node


def test_edit_preserves_structure(osi_adapter):
    adapter, model_path = osi_adapter
    src = adapter.read_metric_source("daily_order_count")
    edited = src.text.replace("Daily order count.", "Edited.")
    res = adapter.write_metric_source("daily_order_count", edited, subject_path=["ops"])
    assert res.created is False
    on_disk = yaml.safe_load(model_path.read_text())
    model = on_disk["semantic_model"][0]
    assert model["metrics"][0]["description"] == "Edited."
    assert model["datasets"][0]["name"] == "raw_orders"


def test_validate_and_delete(osi_adapter):
    adapter, model_path = osi_adapter
    src = adapter.read_metric_source("daily_order_count")
    assert adapter.validate_metric_source(
        src.text, metric_name="daily_order_count"
    ).valid

    res = adapter.delete_metric_source("daily_order_count")
    assert res.deleted is True
    assert yaml.safe_load(model_path.read_text())["semantic_model"][0]["metrics"] == []


def test_authoring_root_falls_back_to_models_dir(tmp_path, make_adapter):
    (tmp_path / "jeff_shop_live.yml").write_text(MODEL)
    # Config with only semantic_models_path (a directory), no explicit file.
    adapter = make_adapter(semantic_model_path=None, semantic_models_path=str(tmp_path))
    assert adapter.read_metric_source("daily_order_count").name == "daily_order_count"

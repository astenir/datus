# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""MetricFlow file-level metric authoring (backward-compat contract)."""

import os
import textwrap

import pytest
import yaml

from datus_semantic_metricflow.authoring import MetricFlowMetricAuthor

SAMPLE = textwrap.dedent(
    """\
    metric:
      name: daily_order_count
      description: "Daily order count"
      type: aggregate
      locked_metadata:
        tags:
        - 'subject_tree: operations/order_volume/daily'
    """
)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "daily_order_count.yml").write_text(SAMPLE)
    return str(tmp_path)


def test_read_returns_metricflow_wrapper(root):
    src = MetricFlowMetricAuthor(root).read("daily_order_count")
    assert src.format == "metricflow"
    doc = yaml.safe_load(src.text)
    assert doc["metric"]["name"] == "daily_order_count"


def test_read_missing_raises(root):
    with pytest.raises(FileNotFoundError):
        MetricFlowMetricAuthor(root).read("nope")


def test_edit_overrides_subject_tree_tag(root):
    author = MetricFlowMetricAuthor(root)
    src = author.read("daily_order_count")
    res = author.write("daily_order_count", src.text, subject_path=["ops", "vol"])
    assert res.created is False
    node = yaml.safe_load(author.read("daily_order_count").text)["metric"]
    assert node["locked_metadata"]["tags"] == ["subject_tree: ops/vol"]


def test_create_writes_metrics_subdir(root):
    author = MetricFlowMetricAuthor(root)
    res = author.write(
        "new_metric",
        "metric:\n  name: new_metric\n  type: aggregate\n",
        subject_path=["a", "b"],
        create=True,
    )
    assert res.created is True
    assert res.file_path == os.path.join(root, "metrics", "new_metric.yml")
    assert os.path.exists(res.file_path)


def test_create_existing_raises(root):
    author = MetricFlowMetricAuthor(root)
    src = author.read("daily_order_count")
    with pytest.raises(ValueError):
        author.write("daily_order_count", src.text, create=True)


def test_delete_removes_single_metric_file(root):
    author = MetricFlowMetricAuthor(root)
    res = author.delete("daily_order_count")
    assert res.deleted is True
    assert not os.path.exists(res.file_path)


def test_validate_ok_and_missing_type(root):
    author = MetricFlowMetricAuthor(root)
    assert author.validate(
        author.read("daily_order_count").text, metric_name="daily_order_count"
    ).valid
    bad = author.validate("metric:\n  name: x\n", metric_name="x")
    assert bad.valid is False


def test_write_accepts_bare_node(root):
    author = MetricFlowMetricAuthor(root)
    res = author.write(
        "daily_order_count", "name: daily_order_count\ndescription: x\ntype: aggregate\n"
    )
    assert res.name == "daily_order_count"


def test_delete_one_of_multiple_metrics_writes_no_null_doc(tmp_path):
    # Consecutive `---` separators produce an explicit empty (None) document;
    # deleting one metric must drop it, never write a literal `null` doc back.
    (tmp_path / "metrics.yml").write_text(
        "---\n---\nmetric:\n  name: a\n  type: aggregate\n---\nmetric:\n  name: b\n  type: aggregate\n"
    )
    assert None in list(yaml.safe_load_all((tmp_path / "metrics.yml").read_text()))  # precondition

    author = MetricFlowMetricAuthor(str(tmp_path))
    author.delete("a")
    raw = (tmp_path / "metrics.yml").read_text()
    assert "null" not in raw
    docs = list(yaml.safe_load_all(raw))
    assert None not in docs
    assert [d["metric"]["name"] for d in docs] == ["b"]


def test_edit_preserves_file_permissions(root):
    import os
    import stat

    target = os.path.join(root, "daily_order_count.yml")
    # A non-default mode so the assertion proves preservation, not the 0644 default.
    os.chmod(target, 0o640)
    author = MetricFlowMetricAuthor(root)
    src = author.read("daily_order_count")
    author.write("daily_order_count", src.text)
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o640


def test_write_rejects_missing_type_before_writing(root):
    import os

    author = MetricFlowMetricAuthor(root)
    before = os.listdir(root)
    with pytest.raises(ValueError, match="missing required field"):
        author.write("daily_order_count", "metric:\n  name: daily_order_count\n")
    assert os.listdir(root) == before  # nothing written


def test_create_rejects_unsafe_metric_name(root):
    author = MetricFlowMetricAuthor(root)
    with pytest.raises(ValueError, match="Unsafe metric name"):
        author.write(
            "../evil",
            "metric:\n  name: ../evil\n  type: aggregate\n",
            create=True,
        )

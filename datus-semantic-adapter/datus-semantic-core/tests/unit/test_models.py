# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for datus_semantic_core.models"""

import pytest
from pydantic import ValidationError

from datus_semantic_core.models import (
    AnomalyContext,
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticModelInfo,
    ValidationIssue,
    ValidationResult,
)


class TestDimensionInfo:
    def test_basic_construction(self):
        dim = DimensionInfo(name="region", description="Sales region")
        assert dim.name == "region"
        assert dim.description == "Sales region"
        assert dim.type is None
        assert dim.is_primary_key is None

    def test_name_only(self):
        dim = DimensionInfo(name="status")
        assert dim.name == "status"
        assert dim.description is None

    def test_with_type(self):
        dim = DimensionInfo(name="status", type="string")
        assert dim.type == "string"

    def test_with_type_time(self):
        dim = DimensionInfo(name="created_at", type="time")
        assert dim.type == "time"

    def test_with_type_categorical(self):
        dim = DimensionInfo(name="segment", type="categorical")
        assert dim.type == "categorical"

    def test_is_primary_key(self):
        dim = DimensionInfo(name="id", type="number", is_primary_key=True)
        assert dim.is_primary_key is True

    def test_all_fields(self):
        dim = DimensionInfo(name="id", description="PK", type="number", is_primary_key=True)
        assert dim.name == "id"
        assert dim.description == "PK"
        assert dim.type == "number"
        assert dim.is_primary_key is True

    def test_serialization_roundtrip(self):
        dim = DimensionInfo(name="x", type="string", is_primary_key=False)
        restored = DimensionInfo(**dim.model_dump())
        assert restored == dim

    def test_backward_compat_no_new_fields(self):
        data = {"name": "old_dim", "description": "old"}
        dim = DimensionInfo(**data)
        assert dim.type is None
        assert dim.is_primary_key is None


class TestSemanticModelInfo:
    def test_minimal(self):
        m = SemanticModelInfo(name="orders")
        assert m.name == "orders"
        assert m.table_name is None
        assert m.dimensions == []
        assert m.measures == []
        assert m.extra == {}

    def test_full(self):
        m = SemanticModelInfo(
            name="orders_cube",
            description="Order cube",
            table_name="orders",
            database_name="analytics",
            platform_type="cube",
            dimensions=[DimensionInfo(name="status", type="string")],
            measures=["orders.count"],
            extra={"connectedComponent": 1},
        )
        assert m.table_name == "orders"
        assert m.database_name == "analytics"
        assert m.platform_type == "cube"
        assert len(m.dimensions) == 1
        assert m.dimensions[0].type == "string"
        assert m.extra["connectedComponent"] == 1

    def test_platform_types(self):
        for pt in ["cube", "view", "explore", "semantic_model"]:
            m = SemanticModelInfo(name="x", platform_type=pt)
            assert m.platform_type == pt

    def test_roundtrip(self):
        m = SemanticModelInfo(
            name="x",
            table_name="x_table",
            dimensions=[DimensionInfo(name="id", type="number", is_primary_key=True)],
            measures=["x.count"],
        )
        restored = SemanticModelInfo(**m.model_dump())
        assert restored == m

    def test_extra_isolation(self):
        m1 = SemanticModelInfo(name="a")
        m2 = SemanticModelInfo(name="b")
        m1.extra["key"] = "val"
        assert "key" not in m2.extra


class TestMetricDefinition:
    def test_basic(self):
        m = MetricDefinition(name="revenue")
        assert m.name == "revenue"
        assert m.dimensions == []
        assert m.measures == []
        assert m.metadata == {}

    def test_full(self):
        m = MetricDefinition(
            name="revenue",
            description="Total revenue",
            type="sum",
            dimensions=["region"],
            measures=["total"],
            unit="USD",
            format="currency",
            path=["Finance"],
            metadata={"cube_name": "orders"},
        )
        assert m.type == "sum"
        assert m.path == ["Finance"]
        assert m.metadata["cube_name"] == "orders"

    def test_arbitrary_depth_path_is_preserved(self):
        path = ["Sales", "Region", "Store", "Promotion"]

        metric = MetricDefinition(name="promo_revenue", path=path)

        assert metric.path == path


class TestQueryResult:
    def test_empty(self):
        qr = QueryResult()
        assert qr.columns == []
        assert qr.data == []
        assert qr.metadata == {}

    def test_with_data(self):
        qr = QueryResult(
            columns=["region", "count"],
            data=[{"region": "US", "count": 100}],
            metadata={"execution_time": 0.5},
        )
        assert len(qr.data) == 1
        assert qr.metadata["execution_time"] == 0.5

    def test_default_collections_are_isolated(self):
        first = QueryResult()
        second = QueryResult()

        first.columns.append("region")
        first.data.append({"region": "US"})
        first.metadata["source"] = "test"

        assert second.columns == []
        assert second.data == []
        assert second.metadata == {}


class TestValidationResult:
    def test_valid(self):
        vr = ValidationResult(valid=True)
        assert vr.valid is True
        assert vr.issues == []

    def test_with_issues(self):
        vr = ValidationResult(
            valid=False,
            issues=[ValidationIssue(severity="error", message="bad config")],
        )
        assert vr.valid is False
        assert len(vr.issues) == 1

    def test_validation_issue_with_location(self):
        issue = ValidationIssue(severity="warning", message="bad join", location="models/orders.yml:42")
        assert issue.location == "models/orders.yml:42"

    def test_validation_issue_rejects_unknown_severity(self):
        with pytest.raises(ValidationError):
            ValidationIssue(severity="fatal", message="unsupported severity")


class TestAnomalyContext:
    def test_basic(self):
        ac = AnomalyContext(rule="wow_gt_20", observed_change_pct=25.5)
        assert ac.rule == "wow_gt_20"
        assert ac.observed_change_pct == 25.5

    def test_anomaly_context_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            AnomalyContext(rule="test", observed_change_pct=10.0, unknown_field="bad")

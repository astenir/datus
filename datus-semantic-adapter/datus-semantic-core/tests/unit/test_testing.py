# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for datus_semantic_core.testing (the contract suite factory)."""

import pytest

from datus_semantic_core.base import BaseSemanticAdapter
from datus_semantic_core.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticModelInfo,
    ValidationIssue,
    ValidationResult,
)
from datus_semantic_core.testing import _resolve_factory, make_semantic_contract_suite


# ---------------------------------------------------------------------------
# Correct adapter — fully spec-compliant
# ---------------------------------------------------------------------------


class _CorrectAdapter(BaseSemanticAdapter):
    """A fully spec-compliant adapter used to verify the contract suite is green."""

    async def list_metrics(self, path=None, limit=100, offset=0):
        data = [
            MetricDefinition(
                name="revenue",
                description="Total revenue",
                dimensions=["date", "region"],
                measures=["revenue_raw"],
                metadata={"source": "fixture"},
            ),
            MetricDefinition(name="orders", dimensions=["date"]),
        ]
        return data[offset : offset + limit]

    async def get_dimensions(self, metric_name, path=None):
        return [
            DimensionInfo(name="date", type="time"),
            DimensionInfo(name="region", type="string"),
        ]

    async def query_metrics(
        self,
        metrics,
        dimensions=None,
        path=None,
        time_start=None,
        time_end=None,
        time_granularity=None,
        where=None,
        limit=None,
        order_by=None,
        dry_run=False,
    ):
        if dry_run:
            return QueryResult(
                columns=["sql"],
                data=[{"sql": "SELECT * FROM revenue"}],
                metadata={"dry_run": True},
            )
        return QueryResult(
            columns=["date", "revenue"],
            data=[
                {"date": "2024-01-01", "revenue": 1000},
                {"date": "2024-01-02", "revenue": 1200},
            ],
            metadata={"execution_time_ms": 12},
        )

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(
            valid=True,
            issues=[
                ValidationIssue(severity="info", message="All good"),
            ],
        )


def _correct_factory():
    return _CorrectAdapter(config=object(), service_type="test")


# Assigning the generated suite to a module-level `Test*` attribute lets
# pytest discover and run it — this verifies the suite is green against a
# spec-compliant adapter.
TestCorrectAdapterContract = make_semantic_contract_suite(
    _correct_factory,
    sample_metric_name="revenue",
    sample_dimension_name="date",
)


# ---------------------------------------------------------------------------
# Broken adapters — each violates one contract clause
# ---------------------------------------------------------------------------


class _BrokenListMetricsReturnsDict(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return {"not": "a list"}  # type: ignore[return-value]

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)


class _BrokenMetricDimensionsAreObjects(BaseSemanticAdapter):
    """MetricDefinition.dimensions should be list[str], not list[DimensionInfo]."""

    async def list_metrics(self, path=None, limit=100, offset=0):
        # Intentionally smuggle DimensionInfo objects in — this would pass
        # Pydantic validation if List[Any] but violates the spec that dims
        # are strings. The contract test enforces this.
        m = MetricDefinition(name="revenue", dimensions=["date"])
        m.dimensions = [DimensionInfo(name="date")]  # type: ignore[list-item]
        return [m]

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)


class _BrokenGetDimensionsReturnsStrings(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return ["date", "region"]  # type: ignore[list-item]

    async def query_metrics(self, metrics, **kwargs):
        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)


class _BrokenQueryDataIsListOfList(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        # list-of-list is a common mistake — core model requires list-of-dict
        return QueryResult.model_construct(
            columns=["date", "revenue"],
            data=[["2024-01-01", 1000]],  # type: ignore[list-item]
            metadata={},
        )

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)


class _BrokenDryRunNoIndicator(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        # Returns a normal result even when dry_run=True — no 'sql' column,
        # no metadata.dry_run flag.
        return QueryResult(
            columns=["date"],
            data=[{"date": "2024-01-01"}],
            metadata={},
        )

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)


class _BrokenValidateReturnsDict(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        return {"valid": True, "issues": []}  # type: ignore[return-value]


def _make_broken_suite(adapter_class):
    return make_semantic_contract_suite(
        lambda: adapter_class(config=object(), service_type="test"),
        sample_metric_name="revenue",
        sample_dimension_name="date",
    )


# ---------------------------------------------------------------------------
# Verify the suite actually catches each violation
# ---------------------------------------------------------------------------


class TestContractSuiteCatchesViolations:
    """Direct invocation of suite methods to verify each violation is detected."""

    @pytest.mark.asyncio
    async def test_catches_list_metrics_wrong_type(self):
        suite_cls = _make_broken_suite(_BrokenListMetricsReturnsDict)
        instance = suite_cls()
        with pytest.raises(AssertionError, match="list_metrics must return a list"):
            await instance.test_list_metrics_returns_list_of_metric_definition()

    @pytest.mark.asyncio
    async def test_catches_metric_dimensions_wrong_entry_type(self):
        suite_cls = _make_broken_suite(_BrokenMetricDimensionsAreObjects)
        instance = suite_cls()
        with pytest.raises(AssertionError, match="dimensions entries must be strings"):
            await instance.test_list_metrics_returns_list_of_metric_definition()

    @pytest.mark.asyncio
    async def test_catches_get_dimensions_returning_strings(self):
        suite_cls = _make_broken_suite(_BrokenGetDimensionsReturnsStrings)
        instance = suite_cls()
        with pytest.raises(
            AssertionError,
            match="DimensionInfo instances",
        ):
            await instance.test_get_dimensions_returns_list_of_dimension_info()

    @pytest.mark.asyncio
    async def test_catches_query_data_rows_not_dicts(self):
        suite_cls = _make_broken_suite(_BrokenQueryDataIsListOfList)
        instance = suite_cls()
        with pytest.raises(AssertionError, match="data rows must be dicts"):
            await instance.test_query_metrics_data_rows_are_dicts()

    @pytest.mark.asyncio
    async def test_catches_dry_run_missing_indicator(self):
        suite_cls = _make_broken_suite(_BrokenDryRunNoIndicator)
        instance = suite_cls()
        with pytest.raises(AssertionError, match="Dry-run query_metrics must either"):
            await instance.test_query_metrics_dry_run_contract()

    @pytest.mark.asyncio
    async def test_catches_validate_semantic_wrong_type(self):
        suite_cls = _make_broken_suite(_BrokenValidateReturnsDict)
        instance = suite_cls()
        with pytest.raises(AssertionError, match="ValidationResult"):
            await instance.test_validate_semantic_returns_validation_result()


# ---------------------------------------------------------------------------
# _resolve_factory edge cases
# ---------------------------------------------------------------------------


class TestResolveFactory:
    @pytest.mark.asyncio
    async def test_accepts_sync_factory(self):
        adapter = await _resolve_factory(_correct_factory)
        assert isinstance(adapter, _CorrectAdapter)

    @pytest.mark.asyncio
    async def test_accepts_async_factory(self):
        async def async_factory():
            return _CorrectAdapter(config=object(), service_type="test")

        adapter = await _resolve_factory(async_factory)
        assert isinstance(adapter, _CorrectAdapter)

    @pytest.mark.asyncio
    async def test_rejects_factory_returning_non_adapter(self):
        with pytest.raises(TypeError, match="BaseSemanticAdapter"):
            await _resolve_factory(lambda: "not an adapter")

    @pytest.mark.asyncio
    async def test_rejects_factory_returning_none(self):
        with pytest.raises(TypeError, match="BaseSemanticAdapter"):
            await _resolve_factory(lambda: None)


# ---------------------------------------------------------------------------
# Verify optional list_semantic_models default is respected
# ---------------------------------------------------------------------------


class _AdapterOverridingOptionalMethods(BaseSemanticAdapter):
    """Adapter that overrides the optional list_semantic_models method."""

    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, **kwargs):
        if kwargs.get("dry_run"):
            return QueryResult(columns=["sql"], data=[{"sql": "SELECT 1"}], metadata={"dry_run": True})
        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        return ValidationResult(valid=True)

    def list_semantic_models(self, catalog_name="", database_name="", schema_name=""):
        return [SemanticModelInfo(name="orders_cube", table_name="orders", platform_type="cube")]


TestAdapterOverridingOptionalMethodsContract = make_semantic_contract_suite(
    lambda: _AdapterOverridingOptionalMethods(config=object(), service_type="test"),
    sample_metric_name="orders",
    sample_dimension_name="date",
)

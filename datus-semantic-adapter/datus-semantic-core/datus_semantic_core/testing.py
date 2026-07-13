# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Reusable contract test suite for semantic adapters.

Any adapter implementing :class:`BaseSemanticAdapter` can reuse this suite to
verify its implementation matches the ``datus-semantic-core`` interface
contract.

Example usage in an adapter package (``tests/unit/test_contract.py``)::

    from unittest.mock import AsyncMock
    from datus_semantic_core.testing import make_semantic_contract_suite
    from datus_semantic_cube import CubeAdapter, CubeConfig

    async def factory():
        config = CubeConfig(api_base_url="http://mock", auth_token="test")
        adapter = CubeAdapter(config)
        # Attach mocks to the instance — each call to factory gets a fresh
        # adapter, so no cross-test state leakage.
        adapter._http_get = AsyncMock(return_value=CUBE_META_FIXTURE)
        return adapter

    TestCubeContract = make_semantic_contract_suite(
        factory,
        sample_metric_name="orders.count",
        sample_dimension_name="orders.status",
    )

``make_semantic_contract_suite`` returns a pytest test class. Assign it to a
module-level name that starts with ``Test`` so pytest discovers it.

Design notes:

- ``pytest`` is imported at module load time. Adapter test modules only import
  ``datus_semantic_core.testing`` from within ``tests/``, so this does not
  force pytest into non-test runtime paths.
- The factory may be sync or async; :func:`_resolve_factory` handles both.
- Each contract test calls the factory independently so mocks and state stay
  isolated between tests.
- Tests assert structural contracts (types, field presence), not specific
  values — adapters can supply whatever test fixtures they like.
"""

import inspect
from typing import Any, Awaitable, Callable, Union

import pytest

from .base import BaseSemanticAdapter
from .models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    ValidationIssue,
    ValidationResult,
)

AdapterFactory = Callable[[], Union[BaseSemanticAdapter, Awaitable[BaseSemanticAdapter]]]


async def _resolve_factory(factory: AdapterFactory) -> BaseSemanticAdapter:
    """Call the factory and await the result if it is awaitable.

    Args:
        factory: Zero-arg callable that returns an adapter (sync) or a
            coroutine resolving to an adapter (async).

    Returns:
        The resolved :class:`BaseSemanticAdapter` instance.

    Raises:
        TypeError: If the factory returns something that is not a
            :class:`BaseSemanticAdapter`.
    """
    result: Any = factory()
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, BaseSemanticAdapter):
        raise TypeError(
            f"adapter_factory must return a BaseSemanticAdapter instance, "
            f"got {type(result).__name__}"
        )
    return result


def make_semantic_contract_suite(
    adapter_factory: AdapterFactory,
    *,
    sample_metric_name: str,
    sample_dimension_name: str,
) -> type:
    """Build a pytest test class that validates a semantic adapter against the spec.

    The returned class contains async tests that exercise every abstract method
    in :class:`BaseSemanticAdapter` and assert the contract defined by the core
    models (:class:`MetricDefinition`, :class:`DimensionInfo`,
    :class:`QueryResult`, :class:`ValidationResult`).

    Args:
        adapter_factory: Zero-arg callable (sync or async) that returns a fully
            initialized adapter instance. Each test calls the factory afresh,
            so the factory should set up fresh mocks / fixtures per call.
        sample_metric_name: A metric name that the adapter (backed by its test
            fixture) is expected to recognize. Passed to ``get_dimensions`` and
            ``query_metrics``.
        sample_dimension_name: A dimension name the adapter is expected to know
            about when backed by the test fixture. Passed to ``query_metrics``.

    Returns:
        A pytest test class. Assign it to a module-level attribute starting
        with ``Test`` in your test module to enable pytest discovery.
    """

    class SemanticAdapterContract:
        """Contract tests for a BaseSemanticAdapter implementation."""

        pytestmark = pytest.mark.asyncio

        # ---- list_metrics --------------------------------------------------

        async def test_list_metrics_returns_list_of_metric_definition(self):
            adapter = await _resolve_factory(adapter_factory)
            metrics = await adapter.list_metrics()
            assert isinstance(metrics, list), (
                f"list_metrics must return a list, got {type(metrics).__name__}"
            )
            for item in metrics:
                assert isinstance(item, MetricDefinition), (
                    "list_metrics items must be MetricDefinition instances, "
                    f"got {type(item).__name__}"
                )
                assert isinstance(item.name, str) and item.name, (
                    "MetricDefinition.name must be a non-empty string"
                )
                assert isinstance(item.dimensions, list), (
                    "MetricDefinition.dimensions must be a list"
                )
                for dim in item.dimensions:
                    assert isinstance(dim, str), (
                        "MetricDefinition.dimensions entries must be strings "
                        "(dimension names), not DimensionInfo — use "
                        f"get_dimensions() for typed info. Got {type(dim).__name__}"
                    )
                assert isinstance(item.measures, list)
                assert isinstance(item.metadata, dict)

        async def test_list_metrics_respects_limit(self):
            adapter = await _resolve_factory(adapter_factory)
            metrics = await adapter.list_metrics(limit=1, offset=0)
            assert isinstance(metrics, list)
            assert len(metrics) <= 1, (
                f"list_metrics(limit=1) must return at most 1 item, got {len(metrics)}"
            )

        # ---- get_dimensions ------------------------------------------------

        async def test_get_dimensions_returns_list_of_dimension_info(self):
            adapter = await _resolve_factory(adapter_factory)
            dims = await adapter.get_dimensions(sample_metric_name)
            assert isinstance(dims, list), (
                f"get_dimensions must return a list, got {type(dims).__name__}"
            )
            for item in dims:
                assert isinstance(item, DimensionInfo), (
                    "get_dimensions items must be DimensionInfo instances, "
                    f"got {type(item).__name__}"
                )
                assert isinstance(item.name, str) and item.name, (
                    "DimensionInfo.name must be a non-empty string"
                )

        # ---- query_metrics -------------------------------------------------

        async def test_query_metrics_returns_query_result(self):
            adapter = await _resolve_factory(adapter_factory)
            result = await adapter.query_metrics(
                metrics=[sample_metric_name],
                dimensions=[sample_dimension_name],
            )
            assert isinstance(result, QueryResult), (
                f"query_metrics must return a QueryResult, got {type(result).__name__}"
            )
            assert isinstance(result.columns, list)
            for col in result.columns:
                assert isinstance(col, str), (
                    f"QueryResult.columns entries must be strings, got {type(col).__name__}"
                )
            assert isinstance(result.data, list)
            assert isinstance(result.metadata, dict)

        async def test_query_metrics_data_rows_are_dicts(self):
            """``QueryResult.data`` must be ``list[dict[str, Any]]`` per core model."""
            adapter = await _resolve_factory(adapter_factory)
            result = await adapter.query_metrics(
                metrics=[sample_metric_name],
                dimensions=[sample_dimension_name],
            )
            for row in result.data:
                assert isinstance(row, dict), (
                    "QueryResult.data rows must be dicts (column -> value), "
                    f"got {type(row).__name__}. See core models.QueryResult."
                )

        async def test_query_metrics_dry_run_contract(self):
            adapter = await _resolve_factory(adapter_factory)
            result = await adapter.query_metrics(
                metrics=[sample_metric_name],
                dimensions=[sample_dimension_name],
                dry_run=True,
            )
            assert isinstance(result, QueryResult)
            # Dry-run must either mark metadata['dry_run'] or expose a 'sql'
            # column — this gives adapters two valid contract shapes.
            has_dry_run_flag = result.metadata.get("dry_run") is True
            has_sql_column = "sql" in result.columns
            assert has_dry_run_flag or has_sql_column, (
                "Dry-run query_metrics must either set metadata['dry_run']=True "
                "or include 'sql' in result.columns"
            )

        # ---- validate_semantic ---------------------------------------------

        async def test_validate_semantic_returns_validation_result(self):
            adapter = await _resolve_factory(adapter_factory)
            result = await adapter.validate_semantic()
            assert isinstance(result, ValidationResult), (
                f"validate_semantic must return a ValidationResult, "
                f"got {type(result).__name__}"
            )
            assert isinstance(result.valid, bool)
            assert isinstance(result.issues, list)
            for issue in result.issues:
                assert isinstance(issue, ValidationIssue), (
                    "ValidationResult.issues entries must be ValidationIssue "
                    f"instances, got {type(issue).__name__}"
                )

        # ---- Optional methods (default implementations return [] / None) --

        async def test_list_semantic_models_returns_list(self):
            """``list_semantic_models`` is sync and has a default impl returning [].

            Adapters that override it must still return a list.
            """
            adapter = await _resolve_factory(adapter_factory)
            models = adapter.list_semantic_models()
            assert isinstance(models, list)

    return SemanticAdapterContract

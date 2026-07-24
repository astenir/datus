# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Engine exception -> core error mapping matrix."""

from __future__ import annotations

import pytest
from _fakes import ExecuteError, FakeEngine, ModelError, QueryError
from datus_semantic_core.exceptions import SemanticCoreException

from datus_semantic_osi_engine.errors import (
    SemanticValidationException,
    raise_mapped,
    validation_error_from_query_error,
)


async def test_query_error_becomes_validation_exception(make_adapter):
    adapter = make_adapter()
    await adapter.list_metrics()  # builds the engine
    error = QueryError(
        'unknown dimension "regionn"',
        code="unknown_dimension",
        candidates=["customers.region"],
    )
    FakeEngine.instances[-1].fail_with = error
    with pytest.raises(SemanticValidationException) as exc:
        await adapter.query_metrics(metrics=["revenue"], dimensions=["regionn"])
    payload = exc.value.payload
    assert payload.code == "unknown_dimension"
    assert payload.metrics == ["revenue"]
    assert payload.unsupported_dimensions == ["regionn"]
    assert payload.suggested_retry == {
        "metrics": ["revenue"],
        "dimensions": ["customers.region"],
    }
    assert "customers.region" in payload.message


async def test_execute_error_becomes_core_exception(make_adapter):
    adapter = make_adapter()
    await adapter.list_metrics()
    FakeEngine.instances[-1].fail_with = ExecuteError(
        "connection refused", code="connection", hint="is the warehouse up?"
    )
    with pytest.raises(SemanticCoreException) as exc:
        await adapter.query_metrics(metrics=["revenue"])
    message = str(exc.value)
    assert "ExecuteError" in message and "connection refused" in message
    assert "is the warehouse up?" in message


def test_ambiguous_dimension_multiple_candidates_no_retry():
    error = QueryError(
        "ambiguous column customer_id",
        code="ambiguous_dimension",
        candidates=["orders.customer_id", "customers.customer_id"],
    )
    payload = validation_error_from_query_error(
        error, requested_metrics=["revenue"], requested_dimensions=["customer_id"]
    )
    assert payload.code == "ambiguous_dimension"
    assert payload.suggested_retry is None  # two candidates: agent must choose
    assert payload.unsupported_dimensions == ["customer_id"]
    assert "orders.customer_id" in payload.message


def test_unknown_metric_single_candidate_retry():
    error = QueryError(
        'unknown metric "revenues"',
        code="unknown_metric",
        metrics=["revenues"],
        candidates=["revenue"],
    )
    payload = validation_error_from_query_error(error, requested_metrics=["revenues"])
    assert payload.suggested_retry == {"metrics": ["revenue"]}
    assert payload.metrics == ["revenues"]


def test_non_retryable_query_error_is_core_exception(fake_binding):
    error = QueryError("planner bug", code="internal")
    with pytest.raises(SemanticCoreException):
        raise_mapped(error, fake_binding)


def test_model_error_is_core_exception(fake_binding):
    error = ModelError("model is invalid:", code="invalid_model")
    with pytest.raises(SemanticCoreException) as exc:
        raise_mapped(error, fake_binding)
    assert "invalid_model" in str(exc.value)


def test_unrelated_error_passes_through(fake_binding):
    with pytest.raises(RuntimeError):
        raise_mapped(RuntimeError("boom"), fake_binding)

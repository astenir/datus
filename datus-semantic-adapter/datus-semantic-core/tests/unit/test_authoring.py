# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""The authoring interface defaults to AuthoringNotSupportedError."""

from unittest.mock import MagicMock

import pytest

from datus_semantic_core.authoring import (
    AuthoringNotSupportedError,
    MetricMutationResult,
    MetricSource,
)
from datus_semantic_core.base import BaseSemanticAdapter


class _ConcreteAdapter(BaseSemanticAdapter):
    async def list_metrics(self, path=None, limit=100, offset=0):
        return []

    async def get_dimensions(self, metric_name, path=None):
        return []

    async def query_metrics(self, metrics, dimensions=None, **kwargs):
        from datus_semantic_core.models import QueryResult

        return QueryResult()

    async def validate_semantic(self, scope: str = "all"):
        from datus_semantic_core.models import ValidationResult

        return ValidationResult(valid=True)


@pytest.fixture
def adapter():
    return _ConcreteAdapter(config=MagicMock(), service_type="test")


def test_read_metric_source_defaults_to_unsupported(adapter):
    with pytest.raises(AuthoringNotSupportedError):
        adapter.read_metric_source("m")


def test_write_metric_source_defaults_to_unsupported(adapter):
    with pytest.raises(AuthoringNotSupportedError):
        adapter.write_metric_source("m", "name: m")


def test_delete_metric_source_defaults_to_unsupported(adapter):
    with pytest.raises(AuthoringNotSupportedError):
        adapter.delete_metric_source("m")


def test_validate_metric_source_defaults_to_unsupported(adapter):
    with pytest.raises(AuthoringNotSupportedError):
        adapter.validate_metric_source("name: m")


def test_authoring_methods_are_not_abstract():
    # A subclass overriding nothing but the query interface is instantiable,
    # proving the authoring methods are optional for third-party adapters.
    _ConcreteAdapter(config=MagicMock())


def test_metric_source_roundtrip_model():
    src = MetricSource(name="m", format="osi", text="name: m")
    assert src.name == "m" and src.semantic_model is None


def test_metric_mutation_result_defaults():
    res = MetricMutationResult(name="m", format="osi", file_path="/tmp/x.yml")
    assert res.created is False and res.deleted is False and res.affected_paths == []

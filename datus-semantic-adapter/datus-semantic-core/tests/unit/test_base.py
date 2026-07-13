# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for datus_semantic_core.base"""

from unittest.mock import MagicMock

import pytest

from datus_semantic_core.base import BaseSemanticAdapter


class _ConcreteAdapter(BaseSemanticAdapter):
    """Minimal concrete adapter for testing."""

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


class TestBaseSemanticAdapterInit:
    def test_stores_config(self):
        config = MagicMock()
        adapter = _ConcreteAdapter(config=config, service_type="test")
        assert adapter.config is config

    def test_stores_service_type(self):
        adapter = _ConcreteAdapter(config=MagicMock(), service_type="cube")
        assert adapter.service_type == "cube"

    def test_extracts_datasource_from_config(self):
        config = MagicMock()
        config.datasource = "prod"
        adapter = _ConcreteAdapter(config=config, service_type="test")
        assert adapter.datasource == "prod"

    def test_datasource_none_when_config_has_no_datasource(self):
        config = object()  # no datasource attribute
        adapter = _ConcreteAdapter(config=config, service_type="test")
        assert adapter.datasource is None

    def test_service_type_fallback_to_config(self):
        config = MagicMock()
        config.service_type = "cube"
        adapter = _ConcreteAdapter(config=config)
        assert adapter.service_type == "cube"

    def test_service_type_empty_when_no_fallback(self):
        config = object()
        adapter = _ConcreteAdapter(config=config)
        assert adapter.service_type == ""


class TestDefaultMethods:
    def test_get_semantic_model_returns_none(self):
        adapter = _ConcreteAdapter(config=MagicMock(), service_type="test")
        assert adapter.get_semantic_model("some_table") is None

    def test_list_semantic_models_returns_empty(self):
        adapter = _ConcreteAdapter(config=MagicMock(), service_type="test")
        assert adapter.list_semantic_models() == []


class TestAbstractEnforcement:
    def test_cannot_instantiate_without_implementing_abstract_methods(self):
        with pytest.raises(TypeError):
            BaseSemanticAdapter(config=MagicMock(), service_type="test")

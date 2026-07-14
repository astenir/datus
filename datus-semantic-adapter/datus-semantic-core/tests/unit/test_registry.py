# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for datus_semantic_core.registry"""

from unittest.mock import MagicMock, patch

import pytest

from datus_semantic_core.base import BaseSemanticAdapter
from datus_semantic_core.config import SemanticAdapterConfig
from datus_semantic_core.exceptions import SemanticCoreException
from datus_semantic_core.registry import AdapterMetadata, SemanticAdapterRegistry


class _DummyConfig(SemanticAdapterConfig):
    service_type: str = "dummy"
    host: str = "localhost"


class _DummyAdapter(BaseSemanticAdapter):
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


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry state before each test."""
    saved_adapters = dict(SemanticAdapterRegistry._adapters)
    saved_factories = dict(SemanticAdapterRegistry._factories)
    saved_metadata = dict(SemanticAdapterRegistry._metadata)
    saved_initialized = SemanticAdapterRegistry._initialized
    yield
    SemanticAdapterRegistry._adapters = saved_adapters
    SemanticAdapterRegistry._factories = saved_factories
    SemanticAdapterRegistry._metadata = saved_metadata
    SemanticAdapterRegistry._initialized = saved_initialized


class TestRegistration:
    def test_register_and_get(self):
        SemanticAdapterRegistry.register(
            service_type="test_dummy",
            adapter_class=_DummyAdapter,
            config_class=_DummyConfig,
            display_name="Test Dummy",
        )
        assert SemanticAdapterRegistry.is_registered("test_dummy")
        meta = SemanticAdapterRegistry.get_metadata("test_dummy")
        assert meta is not None
        assert meta.display_name == "Test Dummy"
        assert meta.adapter_class is _DummyAdapter

    def test_case_insensitive(self):
        SemanticAdapterRegistry.register(
            service_type="CaseMix",
            adapter_class=_DummyAdapter,
        )
        assert SemanticAdapterRegistry.is_registered("casemix")
        assert SemanticAdapterRegistry.is_registered("CASEMIX")

    def test_list_adapters(self):
        SemanticAdapterRegistry.register(service_type="list_test", adapter_class=_DummyAdapter)
        adapters = SemanticAdapterRegistry.list_adapters()
        assert "list_test" in adapters

    def test_create_adapter(self):
        SemanticAdapterRegistry.register(
            service_type="create_test",
            adapter_class=_DummyAdapter,
            config_class=_DummyConfig,
        )
        config = _DummyConfig()
        adapter = SemanticAdapterRegistry.create_adapter("create_test", config)
        assert isinstance(adapter, _DummyAdapter)
        assert adapter.config is config
        assert adapter.service_type == "dummy"  # falls back to config.service_type

    def test_create_adapter_constructor_failure_propagates(self):
        class _FailingAdapter(_DummyAdapter):
            def __init__(self, config):
                raise RuntimeError("init failed")

        SemanticAdapterRegistry.register(service_type="fail_ctor", adapter_class=_FailingAdapter)
        with pytest.raises(RuntimeError, match="init failed"):
            SemanticAdapterRegistry.create_adapter("fail_ctor", _DummyConfig())

    def test_discover_adapters_handles_entry_points_failure(self):
        from unittest.mock import patch

        SemanticAdapterRegistry._initialized = False
        with patch("importlib.metadata.entry_points", side_effect=Exception("broken")):
            SemanticAdapterRegistry.discover_adapters()
        assert SemanticAdapterRegistry._initialized is True

    def test_create_adapter_can_be_satisfied_by_discovery(self):
        discovered = MagicMock(spec=_DummyAdapter)

        def _discover():
            SemanticAdapterRegistry.register(
                service_type="entrypoint_service",
                adapter_class=_DummyAdapter,
                factory=lambda config: discovered,
                config_class=_DummyConfig,
            )

        with (
            patch.object(SemanticAdapterRegistry, "discover_adapters", side_effect=_discover) as mock_discover,
            patch.object(SemanticAdapterRegistry, "_try_load_adapter") as mock_try_load,
        ):
            adapter = SemanticAdapterRegistry.create_adapter("entrypoint_service", _DummyConfig())

        mock_discover.assert_called_once()
        mock_try_load.assert_not_called()
        assert adapter is discovered

    def test_create_adapter_falls_back_to_convention_import_after_discovery(self):
        loaded = MagicMock(spec=_DummyAdapter)

        def _try_load(service_type):
            assert service_type == "convention_service"
            SemanticAdapterRegistry.register(
                service_type="convention_service",
                adapter_class=_DummyAdapter,
                factory=lambda config: loaded,
                config_class=_DummyConfig,
            )

        with (
            patch.object(SemanticAdapterRegistry, "discover_adapters") as mock_discover,
            patch.object(SemanticAdapterRegistry, "_try_load_adapter", side_effect=_try_load) as mock_try_load,
        ):
            adapter = SemanticAdapterRegistry.create_adapter("convention_service", _DummyConfig())

        mock_discover.assert_called_once()
        mock_try_load.assert_called_once_with("convention_service")
        assert adapter is loaded

    def test_try_load_adapter_raises_for_internal_missing_dependency(self):
        missing = ModuleNotFoundError("No module named 'definitely_missing_dependency'")
        missing.name = "definitely_missing_dependency"

        with patch("importlib.import_module", side_effect=missing):
            with pytest.raises(SemanticCoreException, match="missing dependency 'definitely_missing_dependency'"):
                SemanticAdapterRegistry._try_load_adapter("broken")

    def test_try_load_adapter_ignores_missing_top_level_module(self):
        missing = ModuleNotFoundError("No module named 'datus_semantic_absent'")
        missing.name = "datus_semantic_absent"

        with patch("importlib.import_module", side_effect=missing):
            SemanticAdapterRegistry._try_load_adapter("absent")

        assert not SemanticAdapterRegistry.is_registered("absent")

    def test_try_load_adapter_raises_for_generic_import_error(self):
        with patch("importlib.import_module", side_effect=ImportError("bad binary extension")):
            with pytest.raises(SemanticCoreException, match="bad binary extension"):
                SemanticAdapterRegistry._try_load_adapter("broken")


class TestAdapterMetadata:
    def test_get_config_fields(self):
        meta = AdapterMetadata(
            service_type="meta_test",
            adapter_class=_DummyAdapter,
            config_class=_DummyConfig,
            display_name="Meta Test",
        )
        fields = meta.get_config_fields()
        assert "host" in fields
        assert "service_type" in fields

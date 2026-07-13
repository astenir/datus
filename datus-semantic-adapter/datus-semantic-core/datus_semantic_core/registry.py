# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Semantic Adapter Registry (standalone, no agent-1 dependency)."""

import logging
from typing import Any, Callable, Dict, Optional, Type

from datus_semantic_core.base import BaseSemanticAdapter
from datus_semantic_core.exceptions import SemanticCoreException

logger = logging.getLogger(__name__)


class AdapterMetadata:
    """Metadata for a semantic adapter."""

    def __init__(
        self,
        service_type: str,
        adapter_class: Type[BaseSemanticAdapter],
        config_class: Optional[Type] = None,
        display_name: Optional[str] = None,
    ):
        self.service_type = service_type
        self.adapter_class = adapter_class
        self.config_class = config_class
        self.display_name = display_name or service_type.capitalize()

    def get_config_fields(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration fields from Pydantic config model."""
        if not self.config_class:
            return {}

        try:
            from pydantic import BaseModel

            if not issubclass(self.config_class, BaseModel):
                return {}

            fields_info = {}
            for field_name, field_info in self.config_class.model_fields.items():
                field_data = {
                    "required": field_info.is_required(),
                    "default": field_info.default if not field_info.is_required() else None,
                    "description": field_info.description or "",
                    "type": (
                        field_info.annotation.__name__
                        if hasattr(field_info.annotation, "__name__")
                        else str(field_info.annotation)
                    ),
                }

                if hasattr(field_info, "json_schema_extra") and field_info.json_schema_extra:
                    field_data.update(field_info.json_schema_extra)

                fields_info[field_name] = field_data
            return fields_info
        except Exception as e:
            logger.debug(f"Failed to extract config fields for {self.service_type}: {e}")
            return {}


class SemanticAdapterRegistry:
    """Central registry for semantic adapters."""

    _adapters: Dict[str, Type[BaseSemanticAdapter]] = {}
    _factories: Dict[str, Callable] = {}
    _metadata: Dict[str, AdapterMetadata] = {}
    _initialized: bool = False

    @classmethod
    def register(
        cls,
        service_type: str,
        adapter_class: Type[BaseSemanticAdapter],
        factory: Optional[Callable] = None,
        config_class: Optional[Type] = None,
        display_name: Optional[str] = None,
    ):
        """Register a semantic adapter."""
        service_type_lower = service_type.lower()
        cls._adapters[service_type_lower] = adapter_class
        if factory:
            cls._factories[service_type_lower] = factory

        cls._metadata[service_type_lower] = AdapterMetadata(
            service_type=service_type_lower,
            adapter_class=adapter_class,
            config_class=config_class,
            display_name=display_name,
        )

        logger.debug(f"Registered semantic adapter: {service_type} -> {adapter_class.__name__}")

    @classmethod
    def create_adapter(cls, service_type: str, config) -> BaseSemanticAdapter:
        """Create an adapter instance."""
        service_type_lower = service_type.lower()

        if service_type_lower not in cls._adapters:
            cls.discover_adapters()
        if service_type_lower not in cls._adapters:
            cls._try_load_adapter(service_type_lower)

        if service_type_lower not in cls._adapters:
            raise SemanticCoreException(
                f"Semantic adapter '{service_type}' not found. "
                f"Available adapters: {list(cls._adapters.keys())}. "
                f"For additional semantic services, install: pip install datus-semantic-{service_type_lower}"
            )

        if service_type_lower in cls._factories:
            return cls._factories[service_type_lower](config)

        adapter_class = cls._adapters[service_type_lower]
        return adapter_class(config)

    @classmethod
    def _try_load_adapter(cls, service_type: str):
        """Attempt to dynamically load a plugin adapter."""
        import importlib

        module_name = f"datus_semantic_{service_type}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "register"):
                module.register()
                logger.info(f"Dynamically loaded semantic adapter: {service_type}")
        except ModuleNotFoundError as e:
            if e.name == module_name:
                logger.debug(f"No semantic adapter found for: {service_type}")
                return
            raise SemanticCoreException(
                f"Failed to import semantic adapter '{service_type}': missing dependency '{e.name}'"
            ) from e
        except ImportError as e:
            raise SemanticCoreException(
                f"Failed to import semantic adapter '{service_type}': {e}"
            ) from e
        except SemanticCoreException:
            raise
        except Exception as e:
            raise SemanticCoreException(
                f"Failed to load semantic adapter '{service_type}': {e}"
            ) from e

    @classmethod
    def discover_adapters(cls):
        """Auto-discover plugins via Entry Points."""
        if cls._initialized:
            return
        cls._initialized = True

        try:
            from importlib.metadata import entry_points

            try:
                adapter_eps = entry_points(group="datus.semantic_adapters")
            except TypeError:
                eps = entry_points()
                adapter_eps = eps.get("datus.semantic_adapters", [])

            for ep in adapter_eps:
                try:
                    register_func = ep.load()
                    register_func()
                    logger.info(f"Discovered semantic adapter: {ep.name}")
                except Exception as e:
                    logger.warning(f"Failed to load semantic adapter {ep.name}: {e}")
        except Exception as e:
            logger.warning(f"Entry points discovery failed: {e}")

    @classmethod
    def list_adapters(cls) -> Dict[str, Type[BaseSemanticAdapter]]:
        """List all registered adapters."""
        return cls._adapters.copy()

    @classmethod
    def is_registered(cls, service_type: str) -> bool:
        """Check if an adapter is registered."""
        return service_type.lower() in cls._adapters

    @classmethod
    def get_metadata(cls, service_type: str) -> Optional[AdapterMetadata]:
        """Get metadata for a specific adapter."""
        return cls._metadata.get(service_type.lower())

    @classmethod
    def list_available_adapters(cls) -> Dict[str, AdapterMetadata]:
        """List all available adapters with their metadata."""
        cls.discover_adapters()
        return cls._metadata.copy()


# Global instance
semantic_adapter_registry = SemanticAdapterRegistry()

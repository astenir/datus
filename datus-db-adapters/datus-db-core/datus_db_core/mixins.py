# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from abc import ABC, abstractmethod
from typing import Dict, List


class CatalogSupportMixin(ABC):
    """Mixin for databases that support catalog namespace."""

    @abstractmethod
    def get_catalogs(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def switch_catalog(self, catalog_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def default_catalog(self) -> str:
        raise NotImplementedError


class MaterializedViewSupportMixin(ABC):
    """Mixin for databases that support materialized views."""

    @abstractmethod
    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def get_materialized_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        raise NotImplementedError


class SchemaNamespaceMixin(ABC):
    """Mixin for databases that support schema-level namespace."""

    @abstractmethod
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        raise NotImplementedError

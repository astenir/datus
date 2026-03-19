# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for mixins module."""

from typing import Dict, List

import pytest
from datus_db_core.mixins import CatalogSupportMixin, MaterializedViewSupportMixin, SchemaNamespaceMixin


class TestCatalogSupportMixin:
    def test_cannot_instantiate_without_implementation(self):
        with pytest.raises(TypeError):
            CatalogSupportMixin()

    def test_concrete_implementation(self):
        class MyCatalog(CatalogSupportMixin):
            def get_catalogs(self) -> List[str]:
                return ["catalog1", "catalog2"]

            def switch_catalog(self, catalog_name: str) -> None:
                self.current = catalog_name

            def default_catalog(self) -> str:
                return "default"

        obj = MyCatalog()
        assert obj.get_catalogs() == ["catalog1", "catalog2"]
        assert obj.default_catalog() == "default"
        obj.switch_catalog("catalog1")
        assert obj.current == "catalog1"


class TestMaterializedViewSupportMixin:
    def test_cannot_instantiate_without_implementation(self):
        with pytest.raises(TypeError):
            MaterializedViewSupportMixin()

    def test_concrete_implementation(self):
        class MyMV(MaterializedViewSupportMixin):
            def get_materialized_views(self, catalog_name="", database_name="", schema_name="") -> List[str]:
                return ["mv1"]

            def get_materialized_views_with_ddl(
                self, catalog_name="", database_name="", schema_name=""
            ) -> List[Dict[str, str]]:
                return [{"name": "mv1", "ddl": "CREATE MV..."}]

        obj = MyMV()
        assert obj.get_materialized_views() == ["mv1"]
        assert obj.get_materialized_views_with_ddl()[0]["name"] == "mv1"


class TestSchemaNamespaceMixin:
    def test_cannot_instantiate_without_implementation(self):
        with pytest.raises(TypeError):
            SchemaNamespaceMixin()

    def test_concrete_implementation(self):
        class MySchema(SchemaNamespaceMixin):
            def get_schemas(self, catalog_name="", database_name="", include_sys=False) -> List[str]:
                schemas = ["public", "app"]
                if include_sys:
                    schemas.append("information_schema")
                return schemas

        obj = MySchema()
        assert obj.get_schemas() == ["public", "app"]
        assert "information_schema" in obj.get_schemas(include_sys=True)

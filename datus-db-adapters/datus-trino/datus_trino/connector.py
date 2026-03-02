# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Optional, Set, Union, override
from urllib.parse import quote_plus

from datus.tools.db_tools.mixins import CatalogSupportMixin
from datus.utils.loggings import get_logger
from datus_sqlalchemy import SQLAlchemyConnector
from sqlalchemy import create_engine

from .config import TrinoConfig

logger = get_logger(__name__)

TRINO_DIALECT = "trino"


class TrinoConnector(SQLAlchemyConnector, CatalogSupportMixin):
    """
    Trino database connector.

    Trino supports multi-catalog with a three-level hierarchy: catalog -> schema -> table.
    This connector implements CatalogSupportMixin for catalog management.
    """

    def __init__(self, config: Union[TrinoConfig, dict]):
        """
        Initialize Trino connector.

        Args:
            config: TrinoConfig object or dict with configuration
        """
        if isinstance(config, dict):
            config = TrinoConfig(**config)
        elif not isinstance(config, TrinoConfig):
            raise TypeError(f"config must be TrinoConfig or dict, got {type(config)}")

        self.trino_config = config
        self.host = config.host
        self.port = config.port
        self.user = config.username

        # Build connection string: trino://user:pass@host:port/catalog/schema
        encoded_password = quote_plus(config.password) if config.password else ""
        auth_part = f"{config.username}:{encoded_password}@" if config.password else f"{config.username}@"

        connection_string = (
            f"trino://{auth_part}{config.host}:{config.port}"
            f"/{config.catalog}/{config.schema_name}"
            f"?http_scheme={config.http_scheme}"
        )

        super().__init__(connection_string, dialect=TRINO_DIALECT, timeout_seconds=config.timeout_seconds)

        self._verify_ssl = config.verify

        self.dialect = TRINO_DIALECT
        self.catalog_name = config.catalog
        self.schema_name = config.schema_name
        self.database_name = config.schema_name  # In Trino, schemas map to databases

    # ==================== Connection Management ====================

    @override
    def connect(self):
        """Initialize connection pool with SSL verification setting."""
        if self.engine and self._owns_engine:
            return

        self.engine = create_engine(
            self.connection_string,
            pool_size=10,
            max_overflow=20,
            pool_timeout=self.timeout_seconds,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={"verify": self._verify_ssl},
        )
        self._owns_engine = True

    # ==================== Context Manager Support ====================

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()
        return False

    # ==================== Catalog Management (CatalogSupportMixin) ====================

    @override
    def default_catalog(self) -> str:
        """Trino default catalog."""
        return self.trino_config.catalog

    @override
    def get_catalogs(self) -> List[str]:
        """Get list of catalogs."""
        result = self._execute_pandas("SHOW CATALOGS")
        if result.empty:
            return []
        return result.iloc[:, 0].tolist()

    @override
    def switch_catalog(self, catalog_name: str) -> None:
        """Switch to a different catalog.

        Args:
            catalog_name: Name of the catalog to switch to
        """
        self.catalog_name = catalog_name

    # ==================== Metadata Retrieval ====================

    @override
    def _sys_databases(self) -> Set[str]:
        """System databases/schemas to filter out."""
        return {"information_schema"}

    @override
    def _sys_schemas(self) -> Set[str]:
        """System schemas to filter out."""
        return {"information_schema"}

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        """Get list of databases (schemas in Trino)."""
        return self.get_schemas(catalog_name=catalog_name, include_sys=include_sys)

    @override
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        """Get list of schemas from catalog."""
        catalog = catalog_name or self.catalog_name
        result = self._execute_pandas(f'SHOW SCHEMAS FROM "{catalog}"')
        if result.empty:
            return []
        schemas = result.iloc[:, 0].tolist()
        if not include_sys:
            sys_schemas = self._sys_schemas()
            schemas = [s for s in schemas if s.lower() not in sys_schemas]
        return schemas

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of table names."""
        catalog = catalog_name or self.catalog_name
        schema = schema_name or database_name or self.schema_name
        result = self._execute_pandas(f'SHOW TABLES FROM "{catalog}"."{schema}"')
        if result.empty:
            return []
        return result.iloc[:, 0].tolist()

    @override
    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of view names."""
        catalog = catalog_name or self.catalog_name
        schema = schema_name or database_name or self.schema_name
        try:
            result = self._execute_pandas(
                f'SELECT table_name FROM "{catalog}".information_schema.views ' f"WHERE table_schema = '{schema}'"
            )
            if result.empty:
                return []
            return result.iloc[:, 0].tolist()
        except Exception as e:
            logger.warning(f"Failed to get views: {e}")
            return []

    @override
    def get_schema(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> List[Dict[str, Any]]:
        """Get table schema information."""
        if not table_name:
            return []

        catalog = catalog_name or self.catalog_name
        schema = schema_name or database_name or self.schema_name

        sql = (
            f"SELECT column_name, data_type, is_nullable, column_default, comment "
            f'FROM "{catalog}".information_schema.columns '
            f"WHERE table_catalog = '{catalog}' "
            f"AND table_schema = '{schema}' "
            f"AND table_name = '{table_name}' "
            f"ORDER BY ordinal_position"
        )
        query_result = self._execute_pandas(sql)

        result = []
        for i in range(len(query_result)):
            result.append(
                {
                    "cid": i,
                    "name": query_result["column_name"][i],
                    "type": query_result["data_type"][i],
                    "nullable": query_result["is_nullable"][i] == "YES",
                    "default_value": query_result["column_default"][i],
                    "pk": False,  # Trino doesn't have primary keys in INFORMATION_SCHEMA
                    "comment": query_result["comment"][i] if "comment" in query_result.columns else None,
                }
            )
        return result

    # ==================== Full Name Construction ====================

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Safely wrap identifiers with double quotes for Trino."""
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    @override
    def full_name(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> str:
        """
        Build fully-qualified table name.

        Trino format: "catalog"."schema"."table"
        """
        catalog = catalog_name or self.catalog_name
        schema = schema_name or database_name

        if catalog and schema:
            return (
                f"{self._quote_identifier(catalog)}.{self._quote_identifier(schema)}"
                f".{self._quote_identifier(table_name)}"
            )
        elif schema:
            return f"{self._quote_identifier(schema)}.{self._quote_identifier(table_name)}"
        return self._quote_identifier(table_name)

    @override
    def _sqlalchemy_schema(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> Optional[str]:
        """Get schema name for SQLAlchemy Inspector."""
        schema = schema_name or database_name or self.schema_name
        return schema if schema else None

    @override
    def do_switch_context(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        """Switch catalog/schema context."""
        if catalog_name:
            self.catalog_name = catalog_name
        if database_name or schema_name:
            schema = schema_name or database_name
            self.schema_name = schema
            self.database_name = schema

    # ==================== Utility Methods ====================

    def to_dict(self) -> Dict[str, Any]:
        """Convert connector to serializable dictionary."""
        return {
            "db_type": TRINO_DIALECT,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "catalog": self.catalog_name,
            "schema": self.schema_name,
        }

    def get_type(self) -> str:
        """Return the database type."""
        return TRINO_DIALECT

    @override
    def test_connection(self) -> bool:
        """Test the database connection."""
        try:
            return super().test_connection()
        finally:
            try:
                self.close()
            except Exception as e:
                logger.debug(f"Ignoring cleanup error during test: {e}")

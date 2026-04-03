# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, Optional, Set, Union, override

from datus_db_core import get_logger
from datus_postgresql import PostgreSQLConnector

from .config import GreenplumConfig

logger = get_logger(__name__)


def _escape_literal(value: str) -> str:
    """Escape a string for use in SQL string literals (single-quote context)."""
    return value.replace("'", "''")


class GreenplumConnector(PostgreSQLConnector):
    """Greenplum database connector.

    Greenplum is based on PostgreSQL and uses the same wire protocol.
    This connector inherits from PostgreSQLConnector and overrides
    Greenplum-specific behaviors such as system databases/schemas
    and DDL generation with distribution policy.
    """

    def __init__(self, config: Union[GreenplumConfig, dict]):
        """Initialize Greenplum connector.

        Args:
            config: GreenplumConfig object or dict with configuration
        """
        if isinstance(config, dict):
            config = GreenplumConfig(**config)
        elif not isinstance(config, GreenplumConfig):
            raise TypeError(f"config must be GreenplumConfig or dict, got {type(config)}")

        self.greenplum_config = config

        # GreenplumConfig IS-A PostgreSQLConfig, so pass directly to parent
        super().__init__(config)
        # Keep reference to the original Greenplum config
        self.config = config

    # ==================== System Resources ====================

    @override
    def _sys_databases(self) -> Set[str]:
        """System databases to filter out (includes Greenplum-specific databases)."""
        return super()._sys_databases() | {"gpperfmon"}

    @override
    def _sys_schemas(self) -> Set[str]:
        """System schemas to filter out (includes Greenplum-specific schemas)."""
        return super()._sys_schemas() | {
            "gp_toolkit",
            "pg_aoseg",
            "pg_bitmapindex",
        }

    # ==================== DDL Generation ====================

    def _get_distribution_policy(self, schema_name: str, table_name: str) -> Optional[str]:
        """Get distribution policy clause for a Greenplum table.

        Args:
            schema_name: Schema name
            table_name: Table name

        Returns:
            Distribution policy clause string, or None on error
        """
        safe_schema = _escape_literal(schema_name)
        safe_table = _escape_literal(table_name)

        try:
            # GP 4.x uses `attrnums` (int2vector); GP 5+ uses `distkey` (int2[])
            sql = f"""
                SELECT a.attname
                FROM gp_distribution_policy dp
                JOIN pg_class c ON dp.localoid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                LEFT JOIN pg_attribute a ON a.attrelid = c.oid
                    AND a.attnum = ANY(dp.attrnums)
                WHERE n.nspname = '{safe_schema}'
                  AND c.relname = '{safe_table}'
                ORDER BY a.attnum
            """
            result = self._execute_pandas(sql)

            if result.empty or (len(result) == 1 and result["attname"][0] is None):
                return "DISTRIBUTED RANDOMLY"

            dist_cols = [self._quote_identifier(row) for row in result["attname"].tolist() if row is not None]
            if dist_cols:
                return f"DISTRIBUTED BY ({', '.join(dist_cols)})"
            return "DISTRIBUTED RANDOMLY"
        except Exception as e:
            logger.warning(f"Could not get distribution policy for {schema_name}.{table_name}: {e}")
            return None

    @override
    def _get_ddl(self, schema_name: str, table_name: str, object_type: str = "TABLE") -> str:
        """Get DDL for a table/view, including Greenplum distribution policy for tables.

        Args:
            schema_name: Schema name
            table_name: Table name
            object_type: Object type (TABLE, VIEW, MATERIALIZED VIEW)

        Returns:
            DDL statement as string
        """
        ddl = super()._get_ddl(schema_name, table_name, object_type)

        # Append distribution policy for tables
        if object_type == "TABLE" and ddl.startswith("CREATE TABLE"):
            dist_policy = self._get_distribution_policy(schema_name, table_name)
            if dist_policy is not None:
                # Insert distribution policy before the trailing semicolon
                if ddl.endswith(";"):
                    ddl = ddl[:-1] + f"\n{dist_policy};"
                else:
                    ddl += f"\n{dist_policy}"

        return ddl

    # ==================== Storage Info ====================

    def get_storage_info(self, schema_name: str = "", table_name: str = "") -> Optional[Dict[str, Any]]:
        """Get Greenplum-specific storage info for a table.

        Args:
            schema_name: Schema name
            table_name: Table name

        Returns:
            Dictionary with storage info or None
        """
        schema_name = schema_name or self.schema_name
        if not table_name:
            return None

        safe_schema = _escape_literal(schema_name)
        safe_table = _escape_literal(table_name)

        try:
            sql = f"""
                SELECT
                    c.relstorage,
                    CASE c.relstorage
                        WHEN 'h' THEN 'heap'
                        WHEN 'a' THEN 'append-optimized'
                        WHEN 'c' THEN 'column-oriented'
                        WHEN 'x' THEN 'external'
                        ELSE 'unknown'
                    END AS storage_type
                FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = '{safe_schema}'
                  AND c.relname = '{safe_table}'
            """
            result = self._execute_pandas(sql)
            if not result.empty:
                return {
                    "storage_code": result["relstorage"][0],
                    "storage_type": result["storage_type"][0],
                }
        except Exception as e:
            logger.warning(f"Could not get storage info for {schema_name}.{table_name}: {e}")

        return None

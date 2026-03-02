# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Mapping, Optional, Set, Union, override
from urllib.parse import quote_plus

from datus.utils.constants import DBType
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_sqlalchemy import SQLAlchemyConnector
from sqlalchemy import create_engine

from .config import HiveConfig

logger = get_logger(__name__)


class HiveConnector(SQLAlchemyConnector):
    """Hive database connector using SQLAlchemy + PyHive."""

    def __init__(self, config: Union[HiveConfig, dict]):
        """
        Initialize Hive connector.

        Args:
            config: HiveConfig object or dict with configuration
        """
        if isinstance(config, dict):
            config = HiveConfig(**config)
        elif not isinstance(config, HiveConfig):
            raise TypeError(f"config must be HiveConfig or dict, got {type(config)}")

        self.config = config
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.auth = config.auth
        self.configuration = config.configuration or {}

        database = config.database or "default"

        encoded_username = quote_plus(self.username) if self.username else ""
        connection_string = f"hive://{encoded_username}@{self.host}:{self.port}/{database}"

        super().__init__(connection_string, dialect=DBType.HIVE, timeout_seconds=config.timeout_seconds)

        self.database_name = database
        self._connect_args = self._build_connect_args(config)

    @staticmethod
    def _build_connect_args(config: HiveConfig) -> Dict[str, Any]:
        """Build connect_args for PyHive."""
        connect_args: Dict[str, Any] = {}
        if config.auth:
            connect_args["auth"] = config.auth
        if config.password:
            connect_args["password"] = config.password
        if config.configuration:
            connect_args["configuration"] = HiveConnector._normalize_configuration(config.configuration)
        return connect_args

    @staticmethod
    def _normalize_configuration(configuration: Dict[str, Any]) -> Dict[str, str]:
        """Normalize configuration values to strings for PyHive."""
        normalized: Dict[str, str] = {}
        for key, value in configuration.items():
            if value is None:
                normalized[key] = ""
            elif isinstance(value, bool):
                normalized[key] = "true" if value else "false"
            else:
                normalized[key] = str(value)
        return normalized

    @override
    def connect(self):
        """Initialize the SQLAlchemy engine with PyHive connect_args."""
        if self.engine and self._owns_engine:
            return

        try:
            self._safe_close()

            connect_args = dict(self._connect_args)

            if self.dialect not in (DBType.DUCKDB, DBType.SQLITE):
                self.engine = create_engine(
                    self.connection_string,
                    pool_size=10,
                    max_overflow=20,
                    pool_timeout=self.timeout_seconds,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    connect_args=connect_args,
                )
            else:
                self.engine = create_engine(self.connection_string, connect_args=connect_args)

            self.connection = self.engine.connect()
            self._owns_engine = True

        except Exception as e:
            self._force_reset()
            raise self._handle_exception(e, "", "connection") from e

        if not self.engine:
            self._force_reset()
            raise DatusException(
                ErrorCode.DB_CONNECTION_FAILED, message_args={"error_message": "Failed to establish connection"}
            )

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        """Get list of databases in Hive."""
        self.connect()
        result = self._execute_pandas("SHOW DATABASES")
        if result.empty:
            return []

        col_name = result.columns[0]
        databases = [str(value) for value in result[col_name].tolist()]
        if include_sys:
            return databases

        sys_dbs = {name.lower() for name in self._sys_databases()}
        if not sys_dbs:
            return databases
        return [db for db in databases if db.lower() not in sys_dbs]

    def _sys_databases(self) -> Set[str]:
        """Hive system databases to filter out (if any)."""
        return set()

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of tables."""
        self.connect()
        database_name = database_name or self.database_name
        if database_name:
            sql = f"SHOW TABLES IN {self._quote_identifier(database_name)}"
        else:
            sql = "SHOW TABLES"
        result = self._execute_pandas(sql)
        return self._extract_table_names(result)

    @override
    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of views."""
        self.connect()
        database_name = database_name or self.database_name
        if database_name:
            sql = f"SHOW VIEWS IN {self._quote_identifier(database_name)}"
        else:
            sql = "SHOW VIEWS"
        try:
            result = self._execute_pandas(sql)
        except Exception as exc:
            logger.warning("Failed to get Hive views: %s", exc)
            return []
        return self._extract_table_names(result)

    def get_schema(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> List[Dict[str, Any]]:
        """Get table schema information using DESCRIBE."""
        if not table_name:
            return []
        self.connect()
        database_name = database_name or self.database_name
        full_name = self.full_name(database_name=database_name, table_name=table_name)
        result = self._execute_pandas(f"DESCRIBE {full_name}")
        if result.empty:
            return []

        col_name = result.columns[0]
        type_col = result.columns[1] if len(result.columns) > 1 else None
        comment_col = result.columns[2] if len(result.columns) > 2 else None

        rows: List[Dict[str, Any]] = []
        for i in range(len(result)):
            name = str(result[col_name][i]).strip() if result[col_name][i] is not None else ""
            if not name or name.startswith("#"):
                break
            data_type = str(result[type_col][i]).strip() if type_col else ""
            comment = str(result[comment_col][i]).strip() if comment_col else None
            rows.append(
                {
                    "cid": i,
                    "name": name,
                    "type": data_type,
                    "comment": comment,
                    "nullable": True,
                    "pk": False,
                    "default_value": None,
                }
            )
        return rows

    def get_tables_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", tables: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """Get tables with DDL statements."""
        self.connect()
        database_name = database_name or self.database_name
        filter_tables = self._reset_filter_tables(tables, catalog_name, database_name, schema_name)
        result: List[Dict[str, str]] = []
        for table_name in self.get_tables(database_name=database_name):
            full_name = self.full_name(database_name=database_name, table_name=table_name)
            if filter_tables and full_name not in filter_tables:
                continue
            ddl = self._show_create(full_name)
            result.append(
                {
                    "identifier": self.identifier(database_name=database_name, table_name=table_name),
                    "catalog_name": "",
                    "schema_name": "",
                    "database_name": database_name,
                    "table_name": table_name,
                    "table_type": "table",
                    "definition": ddl,
                }
            )
        return result

    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        """Get views with DDL statements."""
        self.connect()
        database_name = database_name or self.database_name
        result: List[Dict[str, str]] = []
        for view_name in self.get_views(database_name=database_name):
            full_name = self.full_name(database_name=database_name, table_name=view_name)
            ddl = self._show_create(full_name)
            result.append(
                {
                    "identifier": self.identifier(database_name=database_name, table_name=view_name),
                    "catalog_name": "",
                    "schema_name": "",
                    "database_name": database_name,
                    "table_name": view_name,
                    "table_type": "view",
                    "definition": ddl,
                }
            )
        return result

    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: str = "table",
    ) -> List[Dict[str, Any]]:
        """Get sample rows from tables."""
        self.connect()
        database_name = database_name or self.database_name
        result: List[Dict[str, Any]] = []
        tables_to_scan = tables or self.get_tables(database_name=database_name)
        for table_name in tables_to_scan:
            full_name = self.full_name(database_name=database_name, table_name=table_name)
            query = f"SELECT * FROM {full_name} LIMIT {top_n}"
            df = self._execute_pandas(query)
            if not df.empty:
                result.append(
                    {
                        "identifier": self.identifier(database_name=database_name, table_name=table_name),
                        "catalog_name": "",
                        "database_name": database_name,
                        "schema_name": "",
                        "table_name": table_name,
                        "table_type": table_type,
                        "sample_rows": df.to_csv(index=False),
                    }
                )
        return result

    def _show_create(self, full_name: str) -> str:
        """Run SHOW CREATE TABLE and return DDL string."""
        df = self._execute_pandas(f"SHOW CREATE TABLE {full_name}")
        if df.empty:
            return f"-- DDL not available for {full_name}"
        ddl_lines = [str(value) for value in df.iloc[:, 0].tolist()]
        return "\n".join(ddl_lines)

    @staticmethod
    def _extract_table_names(result) -> List[str]:
        """Extract table or view names from SHOW TABLES/SHOW VIEWS results."""
        if result.empty:
            return []

        column_map = {str(col).lower(): col for col in result.columns}
        for name in ("tablename", "tab_name", "table_name", "name"):
            if name in column_map:
                col = column_map[name]
                return [str(value) for value in result[col].tolist()]

        for col in result.columns:
            values = result[col].tolist()
            if any(isinstance(value, str) for value in values):
                names = [str(value) for value in values if isinstance(value, str) and value.strip()]
                if names:
                    return names

        for col in result.columns:
            values = result[col].tolist()
            names = [str(value) for value in values if value is not None and not isinstance(value, bool)]
            if names:
                return names

        return []

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Safely wrap identifiers with backticks for Hive."""
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"

    def full_name(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> str:
        """Build fully-qualified table name."""
        db = database_name or self.database_name
        if db:
            return f"{self._quote_identifier(db)}.{self._quote_identifier(table_name)}"
        return self._quote_identifier(table_name)

    def do_switch_context(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        """Switch database context using USE statement."""
        if database_name:
            self._execute_query(f"USE {self._quote_identifier(database_name)}")
            self.database_name = database_name

    @classmethod
    def from_carrier_map(cls, carrier_map: Mapping[str, Any], prefix: str) -> "HiveConnector":
        """Create a HiveConnector from a prefixed carrier map."""
        return cls(HiveConfig.from_config_map(carrier_map, prefix))

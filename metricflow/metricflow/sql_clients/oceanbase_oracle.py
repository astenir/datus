"""MetricFlow SQL client for OceanBase Oracle mode."""

from __future__ import annotations

from typing import Any, ClassVar, List, Optional, Sequence, Tuple

import pandas as pd

from metricflow.configuration.constants import (
    CONFIG_DWH_CONNECT_TIMEOUT_SECONDS,
    CONFIG_DWH_CONNECTION_MODE,
    CONFIG_DWH_DB,
    CONFIG_DWH_DRIVER_CLASS,
    CONFIG_DWH_HOST,
    CONFIG_DWH_JAR_PATH,
    CONFIG_DWH_PASSWORD,
    CONFIG_DWH_PORT,
    CONFIG_DWH_QUERY_TIMEOUT_SECONDS,
    CONFIG_DWH_SCHEMA,
    CONFIG_DWH_USE_SSL,
    CONFIG_DWH_USER,
)
from metricflow.configuration.yaml_handler import YamlFileHandler
from metricflow.dataflow.sql_table import SqlTable
from metricflow.protocols.sql_client import SqlEngine, SqlEngineAttributes, SqlIsolationLevel
from metricflow.protocols.sql_request import SqlJsonTag, SqlRequestTagSet
from metricflow.sql.render.oceanbase_oracle import OceanBaseOracleSqlQueryPlanRenderer
from metricflow.sql.render.sql_plan_renderer import SqlQueryPlanRenderer
from metricflow.sql.sql_bind_parameters import SqlBindParameters
from metricflow.sql_clients.base_sql_client_implementation import BaseSqlClientImplementation
from metricflow.sql_clients.common_client import not_empty


class OceanBaseOracleEngineAttributes:
    """Capabilities verified for the initial read-only OceanBase Oracle profile."""

    sql_engine_type: ClassVar[SqlEngine] = SqlEngine.OCEANBASE_ORACLE

    supported_isolation_levels: ClassVar[Sequence[SqlIsolationLevel]] = ()
    date_trunc_supported: ClassVar[bool] = True
    # Enable only after the real-tenant nightly covers the generated join shape.
    full_outer_joins_supported: ClassVar[bool] = False
    indexes_supported: ClassVar[bool] = False
    multi_threading_supported: ClassVar[bool] = True
    timestamp_type_supported: ClassVar[bool] = True
    timestamp_to_string_comparison_supported: ClassVar[bool] = True
    cancel_submitted_queries_supported: ClassVar[bool] = False
    continuous_percentile_aggregation_supported: ClassVar[bool] = False
    discrete_percentile_aggregation_supported: ClassVar[bool] = False
    approximate_continuous_percentile_aggregation_supported: ClassVar[bool] = False
    approximate_discrete_percentile_aggregation_supported: ClassVar[bool] = False

    double_data_type_name: ClassVar[str] = "BINARY_DOUBLE"
    timestamp_type_name: ClassVar[Optional[str]] = "TIMESTAMP"
    random_function_name: ClassVar[str] = "DBMS_RANDOM.VALUE"

    sql_query_plan_renderer: ClassVar[SqlQueryPlanRenderer] = OceanBaseOracleSqlQueryPlanRenderer()


def _optional_int(value: Optional[str], default: int) -> int:
    return int(value) if value else default


def _config_bool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class OceanBaseOracleSqlClient(BaseSqlClientImplementation):
    """Read-only MetricFlow client backed by the Datus OceanBase Oracle connector."""

    def __init__(self, connector: Any) -> None:
        self._connector = connector
        super().__init__()

    @classmethod
    def from_config(cls, handler: YamlFileHandler) -> OceanBaseOracleSqlClient:
        """Create the client from MetricFlow's normalized configuration."""
        try:
            from datus_oceanbase_oracle import OceanBaseOracleConnector
        except ImportError as exc:
            raise RuntimeError(
                "OceanBase Oracle MetricFlow support requires the optional "
                "`datus-oceanbase-oracle` package."
            ) from exc

        config_url = handler.url
        connector = OceanBaseOracleConnector(
            {
                "host": not_empty(handler.get_value(CONFIG_DWH_HOST), "host", config_url),
                "port": int(not_empty(handler.get_value(CONFIG_DWH_PORT), "port", config_url)),
                "username": not_empty(handler.get_value(CONFIG_DWH_USER), "username", config_url),
                "password": handler.get_value(CONFIG_DWH_PASSWORD) or "",
                "database": handler.get_value(CONFIG_DWH_DB) or None,
                "schema": handler.get_value(CONFIG_DWH_SCHEMA) or None,
                "jar_path": not_empty(handler.get_value(CONFIG_DWH_JAR_PATH), "jar_path", config_url),
                "driver_class": handler.get_value(CONFIG_DWH_DRIVER_CLASS) or "com.oceanbase.jdbc.Driver",
                "connection_mode": handler.get_value(CONFIG_DWH_CONNECTION_MODE) or "odp",
                "use_ssl": _config_bool(handler.get_value(CONFIG_DWH_USE_SSL)),
                "connect_timeout_seconds": _optional_int(
                    handler.get_value(CONFIG_DWH_CONNECT_TIMEOUT_SECONDS), 30
                ),
                "query_timeout_seconds": _optional_int(handler.get_value(CONFIG_DWH_QUERY_TIMEOUT_SECONDS), 30),
            }
        )
        return cls(connector)

    @property
    def sql_engine_attributes(self) -> SqlEngineAttributes:
        return OceanBaseOracleEngineAttributes()

    @staticmethod
    def _to_jdbc_parameters(
        statement: str,
        bind_params: SqlBindParameters,
    ) -> Tuple[str, Tuple[Any, ...]]:
        """Translate MetricFlow named binds to JayDeBeApi's qmark paramstyle."""
        values = bind_params.param_dict
        parameters: List[Any] = []
        rendered: List[str] = []
        index = 0
        quote: Optional[str] = None
        line_comment = False
        block_comment = False

        while index < len(statement):
            char = statement[index]
            following = statement[index + 1] if index + 1 < len(statement) else ""

            if line_comment:
                rendered.append(char)
                if char == "\n":
                    line_comment = False
                index += 1
                continue
            if block_comment:
                rendered.append(char)
                if char == "*" and following == "/":
                    rendered.append(following)
                    block_comment = False
                    index += 2
                else:
                    index += 1
                continue
            if quote:
                rendered.append(char)
                if char == quote:
                    if following == quote:
                        rendered.append(following)
                        index += 2
                        continue
                    quote = None
                index += 1
                continue
            if char == "-" and following == "-":
                rendered.extend((char, following))
                line_comment = True
                index += 2
                continue
            if char == "/" and following == "*":
                rendered.extend((char, following))
                block_comment = True
                index += 2
                continue
            if char in {"'", '"'}:
                rendered.append(char)
                quote = char
                index += 1
                continue
            if char == ":" and (following.isalpha() or following == "_"):
                end = index + 2
                while end < len(statement) and (statement[end].isalnum() or statement[end] == "_"):
                    end += 1
                key = statement[index + 1 : end]
                if key not in values:
                    raise ValueError(f"Missing SQL bind parameter: {key}")
                rendered.append("?")
                parameters.append(values[key])
                index = end
                continue

            rendered.append(char)
            index += 1

        return "".join(rendered), tuple(parameters)

    def _engine_specific_query_implementation(
        self,
        stmt: str,
        bind_params: SqlBindParameters,
        isolation_level: Optional[SqlIsolationLevel] = None,
        system_tags: SqlRequestTagSet = SqlRequestTagSet(),
        extra_tags: SqlJsonTag = SqlJsonTag(),
    ) -> pd.DataFrame:
        statement, parameters = self._to_jdbc_parameters(stmt, bind_params)
        dataframe = self._connector.query_dataframe(statement, parameters)
        return dataframe.rename(columns=lambda column: str(column).lower())

    def _engine_specific_execute_implementation(
        self,
        stmt: str,
        bind_params: SqlBindParameters,
        isolation_level: Optional[SqlIsolationLevel] = None,
        system_tags: SqlRequestTagSet = SqlRequestTagSet(),
        extra_tags: SqlJsonTag = SqlJsonTag(),
    ) -> None:
        raise NotImplementedError("The initial OceanBase Oracle MetricFlow profile is read-only")

    def _engine_specific_dry_run_implementation(self, stmt: str, bind_params: SqlBindParameters) -> None:
        statement = stmt.strip().removesuffix(";")
        statement, parameters = self._to_jdbc_parameters(statement, bind_params)
        self._connector.query_dataframe(
            f"SELECT * FROM (\n{statement}\n) mf_dry_run WHERE 1 = 0",
            parameters,
        )

    def list_tables(self, schema_name: str) -> Sequence[str]:
        return self._connector.get_tables(schema_name=schema_name)

    def create_table_from_dataframe(
        self,
        sql_table: SqlTable,
        df: pd.DataFrame,
        chunk_size: Optional[int] = None,
    ) -> None:
        raise NotImplementedError("The initial OceanBase Oracle MetricFlow profile is read-only")

    def create_schema(self, schema_name: str) -> None:
        raise NotImplementedError("The initial OceanBase Oracle MetricFlow profile is read-only")

    def drop_schema(self, schema_name: str, cascade: bool = True) -> None:
        raise NotImplementedError("The initial OceanBase Oracle MetricFlow profile is read-only")

    def drop_table(self, sql_table: SqlTable) -> None:
        raise NotImplementedError("The initial OceanBase Oracle MetricFlow profile is read-only")

    def cancel_submitted_queries(self) -> None:
        return None

    def cancel_request(self, match_function: Any) -> int:
        return 0

    def close(self) -> None:
        self._connector.close()

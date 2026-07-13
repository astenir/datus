import logging
import threading
import time
from typing import ClassVar, Optional, Sequence, Callable

import pandas as pd
import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool

from metricflow.dataflow.sql_table import SqlTable
from metricflow.protocols.sql_client import SqlEngine, SqlIsolationLevel
from metricflow.protocols.sql_client import SqlEngineAttributes
from metricflow.protocols.sql_request import SqlRequestTagSet, SqlJsonTag
from metricflow.sql.render.sqlite import SqliteSqlQueryPlanRenderer
from metricflow.sql.render.sql_plan_renderer import SqlQueryPlanRenderer
from metricflow.sql.sql_bind_parameters import SqlBindParameters
from metricflow.sql_clients.async_request import CombinedSqlTags
from metricflow.sql_clients.common_client import SqlDialect
from metricflow.sql_clients.sqlalchemy_dialect import SqlAlchemySqlClient

logger = logging.getLogger(__name__)


class SqliteEngineAttributes:
    """Engine-specific attributes for the SQLite query engine"""

    sql_engine_type: ClassVar[SqlEngine] = SqlEngine.SQLITE

    # SQL Engine capabilities
    supported_isolation_levels: ClassVar[Sequence[SqlIsolationLevel]] = ()
    date_trunc_supported: ClassVar[bool] = False  # SQLite doesn't have DATE_TRUNC
    full_outer_joins_supported: ClassVar[bool] = True
    indexes_supported: ClassVar[bool] = True
    multi_threading_supported: ClassVar[bool] = True
    timestamp_type_supported: ClassVar[bool] = True
    timestamp_to_string_comparison_supported: ClassVar[bool] = True
    # Cancelling should be possible, but not yet implemented.
    cancel_submitted_queries_supported: ClassVar[bool] = False
    continuous_percentile_aggregation_supported: ClassVar[bool] = False
    discrete_percentile_aggregation_supported: ClassVar[bool] = False
    approximate_continuous_percentile_aggregation_supported: ClassVar[bool] = False
    approximate_discrete_percentile_aggregation_supported: ClassVar[bool] = False

    # SQL Dialect replacement strings
    double_data_type_name: ClassVar[str] = "DOUBLE"
    timestamp_type_name: ClassVar[Optional[str]] = "TIMESTAMP"
    random_function_name: ClassVar[str] = "RANDOM"

    # MetricFlow attributes
    sql_query_plan_renderer: ClassVar[SqlQueryPlanRenderer] = SqliteSqlQueryPlanRenderer()


class SqliteSqlClient(SqlAlchemySqlClient):
    """Implements SQLite."""

    @staticmethod
    def from_connection_details(url: str, password: Optional[str] = None) -> SqlAlchemySqlClient:  # noqa: D
        parsed_url = sqlalchemy.engine.url.make_url(url)
        dialect = SqlDialect.SQLITE.value
        if parsed_url.drivername != dialect:
            raise ValueError(f"Expected dialect '{dialect}' in {url}")

        if password:
            raise ValueError("Password should be empty")

        return SqliteSqlClient(file_path=parsed_url.database)

    def __init__(self, file_path: Optional[str] = None) -> None:  # noqa: D
        # SQLite is not designed with concurrency, but in can work in multi-threaded settings with
        # check_same_thread=False, StaticPool, and serializing of queries via a lock.
        self._concurrency_lock = threading.Lock()
        super().__init__(
            sqlalchemy.create_engine(
                f"sqlite:///{file_path if file_path else ':memory:'}",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        )

    @property
    def sql_engine_attributes(self) -> SqlEngineAttributes:
        """Collection of attributes and features specific to the SQLite SQL engine"""
        return SqliteEngineAttributes()

    def cancel_submitted_queries(self) -> None:  # noqa: D
        raise NotImplementedError

    def _engine_specific_query_implementation(
        self,
        stmt: str,
        bind_params: SqlBindParameters,
        isolation_level: Optional[SqlIsolationLevel] = None,
        system_tags: SqlRequestTagSet = SqlRequestTagSet(),
        extra_tags: SqlJsonTag = SqlJsonTag(),
    ) -> pd.DataFrame:
        with self._concurrency_lock:
            return super()._engine_specific_query_implementation(
                stmt=stmt, bind_params=bind_params, isolation_level=isolation_level
            )

    def _engine_specific_execute_implementation(
        self,
        stmt: str,
        bind_params: SqlBindParameters,
        isolation_level: Optional[SqlIsolationLevel] = None,
        system_tags: SqlRequestTagSet = SqlRequestTagSet(),
        extra_tags: SqlJsonTag = SqlJsonTag(),
    ) -> None:
        with self._concurrency_lock:
            return super()._engine_specific_execute_implementation(
                stmt=stmt, bind_params=bind_params, isolation_level=isolation_level
            )

    def _engine_specific_dry_run_implementation(self, stmt: str, bind_params: SqlBindParameters) -> None:  # noqa: D
        with self._concurrency_lock:
            return super()._engine_specific_dry_run_implementation(stmt=stmt, bind_params=bind_params)

    def create_table_from_dataframe(  # noqa: D
        self, sql_table: SqlTable, df: pd.DataFrame, chunk_size: Optional[int] = None
    ) -> None:
        # SQLite doesn't really have schemas, so we ignore the schema_name
        with self._concurrency_lock:
            logger.info(f"Creating table '{sql_table.table_name}' from a DataFrame with {df.shape[0]} row(s)")
            start_time = time.time()
            with self._engine_connection(self._engine) as conn:
                pd.io.sql.to_sql(
                    frame=df,
                    name=sql_table.table_name,
                    con=conn,
                    index=False,
                    if_exists="fail",
                    method="multi",
                    chunksize=chunk_size,
                )
            logger.info(f"Created table '{sql_table.table_name}' from a DataFrame in {time.time() - start_time:.2f}s")

    def cancel_request(self, match_function: Callable[[CombinedSqlTags], bool]) -> int:  # noqa: D
        raise NotImplementedError

    def create_schema(self, schema_name: str) -> None:  # noqa: D
        # SQLite doesn't have schemas, so we just ensure the database exists
        # The database is automatically created when we connect, so no action needed
        pass

    def list_tables(self, schema_name: str) -> Sequence[str]:  # noqa: D
        with self._concurrency_lock:
            insp = inspect(self._engine)
            # SQLite doesn't really have schemas, so we just return all tables
            return insp.get_table_names()

    def generate_health_check_tests(self, schema_name: str):  # noqa: D
        # Override to avoid schema prefixes in table names for SQLite
        table_name = "health_report"
        return [
            ("SELECT 1", lambda: self.execute("SELECT 1")),
            (f"Create schema '{schema_name}'", lambda: self.create_schema(schema_name)),
            (
                f"Create table '{table_name}' with a SELECT",
                lambda: self.create_table_as_select(
                    SqlTable(schema_name="", table_name=table_name), "SELECT 'test' AS test_col"
                ),
            ),
            (
                f"Drop table '{table_name}'",
                lambda: self.drop_table(SqlTable(schema_name="", table_name=table_name)),
            ),
        ]

    def create_table_as_select(  # noqa: D
        self,
        sql_table: SqlTable,
        select_query: str,
        sql_bind_parameters: SqlBindParameters = SqlBindParameters(),
    ) -> None:
        # For SQLite, ignore schema and just use table name
        table_name = sql_table.table_name
        self.execute(
            f"CREATE TABLE {table_name} AS {select_query}",
            sql_bind_parameters=sql_bind_parameters,
        )

    def drop_table(self, sql_table: SqlTable) -> None:  # noqa: D
        # For SQLite, ignore schema and just use table name
        table_name = sql_table.table_name
        self.execute(f"DROP TABLE IF EXISTS {table_name}")

    def table_exists(self, sql_table: SqlTable) -> bool:  # noqa: D
        # For SQLite, ignore schema and just check if table name exists
        return sql_table.table_name in self.list_tables("")

"""
Service for handling CLI Command operations.
"""

import asyncio
import re
import threading
import time
import uuid
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Callable, Dict, Optional, Sequence

from datus.api.models.base_models import Result
from datus.api.models.cli_models import (
    ContextResultData,
    ExecuteContextData,
    ExecuteContextInput,
    ExecuteSQLData,
    ExecuteSQLInput,
    InternalCommandData,
    InternalCommandInput,
    InternalCommandResultData,
    StopExecuteSQLData,
    TableInfo,
)
from datus.api.models.config_models import ErrorCode
from datus.api.services.chat_service import ChatService
from datus.configuration.agent_config_loader import AgentConfig
from datus.schemas.action_history import (
    ActionHistory,
    ActionHistoryManager,
    ActionRole,
    ActionStatus,
)
from datus.tools.db_tools import db_manager as db_manager_module
from datus.tools.db_tools.db_manager import DBManager
from datus.tools.func_tool.database import DBFuncTool
from datus.utils.constants import SQLType
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso

logger = get_logger(__name__)


@dataclass
class _SQLTaskRecord:
    task: asyncio.Task
    owner_user_id: Optional[str]


def _scope_patterns(grant: dict, scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    return [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]


def _compose_scope_tokens(
    field_order: Optional[Sequence[str]],
    *,
    catalogs: Optional[list[str]] = None,
    databases: Optional[list[str]] = None,
    schemas: Optional[list[str]] = None,
    tables: Optional[list[str]] = None,
) -> list[str]:
    ordered_fields = list(field_order or ("catalog", "database", "schema", "table"))
    if "table" not in ordered_fields:
        ordered_fields.append("table")

    constrained_fields = [
        field
        for field, values in (("catalog", catalogs), ("database", databases), ("schema", schemas), ("table", tables))
        if values is not None and field in ordered_fields
    ]
    if not constrained_fields:
        return ["*"]

    start_index = min(ordered_fields.index(field) for field in constrained_fields)
    scoped_fields = ordered_fields[start_index:]
    catalog_values = catalogs if catalogs is not None and "catalog" in scoped_fields else [None]
    database_values = databases if databases is not None and "database" in scoped_fields else [None]
    schema_values = schemas if schemas is not None and "schema" in scoped_fields else [None]
    table_values = tables if tables is not None else ["*"]

    tokens: list[str] = []
    for catalog in catalog_values:
        for database in database_values:
            for schema in schema_values:
                for table in table_values:
                    values = {
                        "catalog": catalog,
                        "database": database,
                        "schema": schema,
                        "table": table,
                    }
                    parts = [values.get(field) or "*" for field in scoped_fields]
                    tokens.append(".".join(parts))
    return tokens


def _schema_qualified_dialect(dialect: str) -> bool:
    # Keep this aligned with extract_table_names(..., ignore_empty=True): these
    # dialects can emit two-part schema.table names while the active database
    # still comes from the connector context.
    return (dialect or "").strip().lower() in {
        "postgres",
        "postgresql",
        "redshift",
        "greenplum",
        "snowflake",
        "duckdb",
        "oracle",
        "mssql",
        "sqlserver",
    }


def _catalog_qualified_dialect(dialect: str) -> bool:
    return (dialect or "").strip().lower() in {"starrocks"}


_SHOW_NAMESPACE_RE = re.compile(
    r"^\s*SHOW\s+(?:FULL\s+)?(?P<kind>TABLES|VIEWS|DATABASES|SCHEMAS)\s+(?:FROM|IN)\s+(?P<target>[^\s;]+)",
    flags=re.IGNORECASE,
)
_SHOW_TABLE_TARGET_RE = re.compile(
    r"^\s*SHOW\s+(?:FULL\s+)?(?:COLUMNS|FIELDS|INDEX|INDEXES|KEYS)\s+"
    r"(?:FROM|IN)\s+(?P<target>[^\s;]+)(?:\s+(?:FROM|IN)\s+(?P<namespace>[^\s;]+))?",
    flags=re.IGNORECASE,
)
_SHOW_CREATE_TARGET_RE = re.compile(
    r"^\s*SHOW\s+CREATE\s+(?:TABLE|VIEW)\s+(?P<target>[^\s;]+)",
    flags=re.IGNORECASE,
)


class CLIService:
    """Service for handling CLI command operations."""

    def __init__(self, agent_config: Optional[AgentConfig] = None, chat_service: Optional[ChatService] = None):
        """
        Initialize the CLI service.

        Args:
            agent_config: Datus agent configuration
        """
        self.agent_config = agent_config
        self.chat_service = chat_service
        # Initialize database manager and datasource only if agent_config is provided
        if self.agent_config:
            self.db_manager = DBManager(self.agent_config.datasource_configs)
            self.current_datasource = self.agent_config.current_datasource
        else:
            self.db_manager = None
            self.current_datasource = None

        # Initialize CLI context first (before _initialize_connection)
        from datus.cli.cli_context import CliContext

        self.current_db_name = None
        self.cli_context = CliContext(
            current_db_name="",
            current_catalog="",
            current_schema="",
        )

        # Initialize database connection
        self.current_db_connector = None
        if self.agent_config:
            self._initialize_connection()

        # Track running SQL execution tasks with request-owner metadata.
        self._sql_tasks: Dict[str, _SQLTaskRecord] = {}
        self._sql_tasks_lock = threading.Lock()

    def _initialize_connection(self):
        """Initialize the current database connection."""
        if self.db_manager and self.current_datasource:
            try:
                db_name, connector = self.db_manager.first_conn_with_name(self.current_datasource)
                self.current_db_connector = connector
                self.current_db_name = db_name

                # Update CLI context with connection info
                if self.cli_context and connector:
                    self.cli_context.update_database_context(
                        catalog=getattr(connector, "catalog_name", ""),
                        db_name=db_name or "",
                        schema=getattr(connector, "schema_name", ""),
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize database connection: {e}")

    def _cleanup_sql_task(self, task_id: str) -> None:
        """Remove a completed SQL task from the tracking dict."""
        with self._sql_tasks_lock:
            self._sql_tasks.pop(task_id, None)

    def _execute_sql_sync(
        self,
        request: ExecuteSQLInput,
        task_id: str,
        agent_config: Optional[AgentConfig] = None,
    ) -> Result[ExecuteSQLData]:
        """Synchronous SQL execution logic (runs in a thread)."""
        try:
            connector, current_db_name, cleanup_connector = self._execution_connector(agent_config)
            if not connector:
                return Result(
                    success=False,
                    errorCode=ErrorCode.DATABASE_CONNECTION_ERROR,
                    errorMessage="No database connection available",
                )

            try:
                effective_database = request.database_name or current_db_name
                denial = self._database_grant_denial(agent_config, effective_database)
                if denial:
                    return Result(
                        success=False,
                        errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                        errorMessage=denial,
                    )

                # Switch to the requested database/catalog context before executing.
                if request.database_name:
                    self._switch_connector_database(connector, request.database_name)

                sql_query = self._authorize_read_sql(request.sql_query, connector, agent_config)
                if isinstance(sql_query, Result):
                    return sql_query

                # Create action for SQL execution (local to avoid cross-request state)
                actions = ActionHistoryManager()
                sql_action = ActionHistory.create_action(
                    role=ActionRole.USER,
                    action_type="sql_execution",
                    messages=(
                        f"Executing SQL: {sql_query[:100]}..."
                        if len(sql_query) > 100
                        else f"Executing SQL: {sql_query}"
                    ),
                    input_data={"sql": sql_query, "system": request.system},
                    status=ActionStatus.PROCESSING,
                )
                actions.add_action(sql_action)

                # Execute the query
                start_time = time.time()
                result = connector.execute(
                    input_params={"sql_query": sql_query},
                    result_format=request.result_format,
                )
                end_time = time.time()
                exec_time = end_time - start_time

                if not result:
                    actions.update_action_by_id(
                        sql_action.action_id,
                        status=ActionStatus.FAILED,
                        output={"error": "No result from query"},
                        messages="SQL execution failed: No result from query",
                    )
                    return Result(
                        success=False,
                        errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                        errorMessage="No result from the query",
                    )

                if result.success:
                    sql_return = None
                    row_count = None
                    columns = None

                    if hasattr(result.sql_return, "column_names"):
                        if request.result_format == "csv":
                            import csv
                            import io

                            rows = result.sql_return.to_pylist()
                            output = io.StringIO()
                            if rows:
                                writer = csv.DictWriter(output, fieldnames=result.sql_return.column_names)
                                writer.writeheader()
                                writer.writerows(rows)
                            sql_return = output.getvalue()
                        elif request.result_format == "json":
                            import json

                            rows = result.sql_return.to_pylist()
                            sql_return = json.dumps(rows)
                        else:
                            sql_return = str(result.sql_return)

                        row_count = result.sql_return.num_rows
                        columns = result.sql_return.column_names
                    else:
                        sql_return = str(result.sql_return) if result.sql_return else ""
                        row_count = result.row_count

                    actions.update_action_by_id(
                        sql_action.action_id,
                        status=ActionStatus.SUCCESS,
                        output={
                            "row_count": row_count,
                            "execution_time": exec_time,
                            "columns": columns,
                            "success": True,
                        },
                        messages=f"SQL executed successfully: {row_count or 0} rows in {exec_time:.2f}s",
                    )

                    data = ExecuteSQLData(
                        execute_task_id=task_id,
                        sql_query=sql_query,
                        row_count=row_count,
                        sql_return=sql_return,
                        result_format=request.result_format,
                        execution_time=exec_time,
                        executed_at=now_utc_iso(),
                        columns=columns,
                    )

                    return Result(success=True, data=data)
                else:
                    error_msg = result.error or "Unknown SQL error"

                    actions.update_action_by_id(
                        sql_action.action_id,
                        status=ActionStatus.FAILED,
                        output={"error": error_msg, "sql_error": True},
                        messages=f"SQL error: {error_msg}",
                    )

                    return Result(
                        success=False,
                        errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                        errorMessage=error_msg,
                    )
            finally:
                if cleanup_connector:
                    cleanup_connector()

        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=str(e),
            )

    def _execution_connector(self, agent_config: Optional[AgentConfig] = None):
        if agent_config is None:
            return self.current_db_connector, self.current_db_name, None
        db_manager, cleanup = self._request_scoped_db_manager(agent_config.datasource_configs)
        datasource = getattr(agent_config, "current_datasource", "") or ""
        db_name, connector = db_manager.first_conn_with_name(datasource)
        return connector, db_name, cleanup

    @staticmethod
    def _request_scoped_db_manager(datasource_configs: dict) -> tuple[DBManager, Optional[Callable[[], None]]]:
        if db_manager_module._factory is not None:
            return db_manager_module.db_manager_instance(datasource_configs), None
        db_manager = DBManager(datasource_configs)
        return db_manager, db_manager.close

    @staticmethod
    def _switch_connector_database(connector, database_name: str) -> None:
        catalog = getattr(connector, "catalog_name", "") or ""
        connector.switch_context(
            catalog_name=catalog,
            database_name=database_name,
        )
        try:
            connector.database_name = database_name
        except Exception:
            pass

    @staticmethod
    def _authorize_read_sql(sql: str, connector, agent_config: Optional[AgentConfig]) -> str | Result[ExecuteSQLData]:
        guard = object.__new__(DBFuncTool)
        guard._primary_connector = connector
        guard.agent_config = agent_config
        principal = getattr(agent_config, "principal", {}) if agent_config is not None else {}
        guard.principal = dict(principal) if isinstance(principal, dict) else {}
        guard.sub_agent_name = None
        guard._field_order = CLIService._field_order_for_grant(
            guard._determine_field_order(),
            agent_config,
            dialect=getattr(connector, "dialect", "") or "",
        )
        scoped_tables = CLIService._scoped_table_patterns(agent_config, guard._field_order)
        guard._scoped_patterns = guard._load_scoped_patterns(scoped_tables)

        validation_error, sql_type = guard._validate_read_sql(sql, connector)
        if validation_error:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=validation_error.error,
            )
        metadata_denial = CLIService._metadata_scope_denial(sql, sql_type, connector, agent_config, guard)
        if metadata_denial:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=metadata_denial,
            )

        datasource = str(guard.principal.get("datasource") or getattr(agent_config, "current_datasource", "") or "")
        try:
            rewritten_sql = guard._enforce_sql_policy(
                sql,
                datasource=datasource or "default",
                dialect=getattr(connector, "dialect", "") or "",
            )
        except DatusException as exc:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=str(exc),
            )
        validation_error, rewritten_sql_type = guard._validate_read_sql(rewritten_sql, connector)
        if validation_error:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=validation_error.error,
            )
        metadata_denial = CLIService._metadata_scope_denial(
            rewritten_sql,
            rewritten_sql_type,
            connector,
            agent_config,
            guard,
        )
        if metadata_denial:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=metadata_denial,
            )
        return rewritten_sql

    @staticmethod
    def _metadata_scope_denial(
        sql: str,
        sql_type: SQLType,
        connector,
        agent_config: Optional[AgentConfig],
        guard: DBFuncTool,
    ) -> Optional[str]:
        if sql_type != SQLType.METADATA_SHOW:
            return None
        _datasource, grant = CLIService._current_datasource_grant(agent_config)
        if not isinstance(grant, dict):
            return None
        scoped_keys = ("catalogs", "databases", "schemas", "tables")
        if not any(_scope_patterns(grant, key) is not None for key in scoped_keys):
            return None

        from datus.utils.sql_utils import _first_statement, extract_table_names

        dialect = getattr(connector, "dialect", "") or ""
        if extract_table_names(sql, dialect=dialect, ignore_empty=True):
            return None

        statement = _first_statement(sql).strip()
        target = CLIService._metadata_scope_target(statement)
        if not target:
            return "Metadata SQL requires an authorized target under scoped datasource grants."

        coordinate = guard._build_table_coordinate(raw_name=target)
        if guard._table_matches_scope(coordinate):
            return None
        return f"Metadata SQL target is outside scoped context: {target}"

    @staticmethod
    def _metadata_scope_target(statement: str) -> str:
        match = _SHOW_CREATE_TARGET_RE.match(statement)
        if match:
            return match.group("target").strip().strip(";")

        match = _SHOW_TABLE_TARGET_RE.match(statement)
        if match:
            target = match.group("target").strip().strip(";")
            namespace = (match.group("namespace") or "").strip().strip(";")
            if namespace:
                if "." in target:
                    return ""
                return f"{namespace}.{target}"
            return target

        match = _SHOW_NAMESPACE_RE.match(statement)
        if not match:
            return ""
        target = match.group("target").strip().strip(";")
        if not target:
            return ""
        kind = match.group("kind").strip().upper()
        if kind in {"DATABASES", "SCHEMAS"}:
            return f"{target}.*.*"
        return f"{target}.*"

    @staticmethod
    def _database_grant_denial(agent_config: Optional[AgentConfig], database_name: Optional[str]) -> Optional[str]:
        datasource, grant = CLIService._current_datasource_grant(agent_config)
        if grant is True:
            return None
        if grant is None:
            return None
        if not isinstance(grant, dict):
            return f"Datasource '{datasource}' is not authorized for this request."

        patterns = _scope_patterns(grant, "databases")
        if patterns is None:
            return None
        requested_database = (database_name or "").strip()
        if not requested_database:
            return None
        if patterns and any(fnmatchcase(requested_database, pattern) for pattern in patterns):
            return None
        return f"Requested database '{requested_database}' is not authorized for datasource '{datasource}'."

    @staticmethod
    def _filter_database_names_by_grant(
        database_names: Sequence[str], agent_config: Optional[AgentConfig]
    ) -> list[str]:
        _datasource, grant = CLIService._current_datasource_grant(agent_config)
        if not isinstance(grant, dict):
            return list(database_names)

        patterns = _scope_patterns(grant, "databases")
        if patterns is None:
            return list(database_names)
        if not patterns:
            return []
        return [
            database_name
            for database_name in database_names
            if any(fnmatchcase(database_name, pattern) for pattern in patterns)
        ]

    @staticmethod
    def _field_order_for_grant(
        field_order: Sequence[str],
        agent_config: Optional[AgentConfig],
        *,
        dialect: str = "",
    ) -> Sequence[str]:
        order = list(field_order)
        _datasource, grant = CLIService._current_datasource_grant(agent_config)
        if not isinstance(grant, dict):
            return order

        has_catalog_scope = _scope_patterns(grant, "catalogs") is not None
        has_database_scope = _scope_patterns(grant, "databases") is not None
        has_schema_scope = _scope_patterns(grant, "schemas") is not None
        if has_catalog_scope and "catalog" not in order:
            database_index = order.index("database") if "database" in order else len(order)
            table_index = order.index("table") if "table" in order else len(order)
            order.insert(min(database_index, table_index), "catalog")
        if has_catalog_scope and _catalog_qualified_dialect(dialect) and "database" not in order:
            table_index = order.index("table") if "table" in order else len(order)
            order.insert(table_index, "database")
        if has_database_scope and "database" not in order:
            table_index = order.index("table") if "table" in order else len(order)
            order.insert(table_index, "database")
        if (has_schema_scope or (has_database_scope and _schema_qualified_dialect(dialect))) and "schema" not in order:
            table_index = order.index("table") if "table" in order else len(order)
            order.insert(table_index, "schema")
        return order

    @staticmethod
    def _scoped_table_patterns(
        agent_config: Optional[AgentConfig],
        field_order: Optional[Sequence[str]] = None,
    ) -> Optional[list[str]]:
        _datasource, grant = CLIService._current_datasource_grant(agent_config)
        if not isinstance(grant, dict):
            return None

        table_patterns = _scope_patterns(grant, "tables")
        schema_patterns = _scope_patterns(grant, "schemas")
        database_patterns = _scope_patterns(grant, "databases")
        catalog_patterns = _scope_patterns(grant, "catalogs")
        if table_patterns is not None:
            if not table_patterns:
                return ["__NO_TABLES_ALLOWED__"]
            if catalog_patterns == []:
                return ["__NO_CATALOGS_ALLOWED__"]
            if database_patterns == []:
                return ["__NO_DATABASES_ALLOWED__"]
            if schema_patterns == []:
                return ["__NO_SCHEMAS_ALLOWED__"]
            return _compose_scope_tokens(
                field_order,
                catalogs=catalog_patterns,
                databases=database_patterns,
                schemas=schema_patterns,
                tables=table_patterns,
            )

        if schema_patterns is not None:
            if not schema_patterns:
                return ["__NO_SCHEMAS_ALLOWED__"]
            if catalog_patterns == []:
                return ["__NO_CATALOGS_ALLOWED__"]
            if database_patterns == []:
                return ["__NO_DATABASES_ALLOWED__"]
            return _compose_scope_tokens(
                field_order,
                catalogs=catalog_patterns,
                databases=database_patterns,
                schemas=schema_patterns,
            )
        if database_patterns is not None:
            if not database_patterns:
                return ["__NO_DATABASES_ALLOWED__"]
            if catalog_patterns == []:
                return ["__NO_CATALOGS_ALLOWED__"]
            return _compose_scope_tokens(field_order, catalogs=catalog_patterns, databases=database_patterns)
        if catalog_patterns is not None:
            if not catalog_patterns:
                return ["__NO_CATALOGS_ALLOWED__"]
            return _compose_scope_tokens(field_order, catalogs=catalog_patterns)
        return None

    @staticmethod
    def _filter_table_names_by_grant(
        table_names: Sequence[str], connector, agent_config: Optional[AgentConfig]
    ) -> list[str]:
        guard = object.__new__(DBFuncTool)
        guard._primary_connector = connector
        guard.agent_config = agent_config
        guard.sub_agent_name = None
        guard._field_order = CLIService._field_order_for_grant(
            guard._determine_field_order(),
            agent_config,
            dialect=getattr(connector, "dialect", "") or "",
        )
        scoped_tables = CLIService._scoped_table_patterns(agent_config, guard._field_order)
        guard._scoped_patterns = guard._load_scoped_patterns(scoped_tables)
        if not guard._scoped_patterns:
            return list(table_names)
        return [
            table_name
            for table_name in table_names
            if guard._table_matches_scope(
                guard._build_table_coordinate(raw_name=table_name, connector=connector),
            )
        ]

    @staticmethod
    def _current_datasource_grant(agent_config: Optional[AgentConfig]) -> tuple[str, object | None]:
        if agent_config is None:
            return "", None
        principal = getattr(agent_config, "principal", {}) or {}
        if not isinstance(principal, dict):
            return "", None
        datasource_grants = principal.get("datasource_grants")
        if not isinstance(datasource_grants, dict) or not datasource_grants:
            return "", None
        datasource = str(principal.get("datasource") or getattr(agent_config, "current_datasource", "") or "")
        return datasource, datasource_grants.get(datasource)

    async def execute_sql(
        self,
        request: ExecuteSQLInput,
        user_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> Result[ExecuteSQLData]:
        """Execute SQL query asynchronously with cancellation support.

        If ``request.execute_task_id`` is provided, it is used as-is and returned
        unchanged in ``ExecuteSQLData`` so the caller can cancel the execution
        via ``stop_execute_sql()``. Otherwise a server-generated UUID is used.
        """
        task_id = request.execute_task_id or str(uuid.uuid4())

        async def _run() -> Result[ExecuteSQLData]:
            try:
                return await asyncio.to_thread(self._execute_sql_sync, request, task_id, agent_config)
            except asyncio.CancelledError:
                logger.info(f"SQL execution task cancelled: {task_id}")
                return Result(
                    success=False,
                    errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                    errorMessage="SQL execution was cancelled",
                )
            finally:
                self._cleanup_sql_task(task_id)

        with self._sql_tasks_lock:
            if task_id in self._sql_tasks:
                return Result(
                    success=False,
                    errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                    errorMessage=f"execute_task_id '{task_id}' is already in use",
                )
            task = asyncio.create_task(_run())
            self._sql_tasks[task_id] = _SQLTaskRecord(task=task, owner_user_id=user_id)

        return await task

    async def stop_execute_sql(self, task_id: str, user_id: Optional[str] = None) -> Result[StopExecuteSQLData]:
        """Stop a running SQL execution task.

        Args:
            task_id: The execute_task_id returned from execute_sql.

        Returns:
            Result indicating whether the task was stopped.
        """
        with self._sql_tasks_lock:
            record = self._sql_tasks.get(task_id)

        if not record or (user_id is not None and record.owner_user_id != user_id):
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=f"No running SQL execution found for task ID: {task_id}",
                data=StopExecuteSQLData(execute_task_id=task_id, stopped=False),
            )

        task = record.task
        if task.done():
            self._cleanup_sql_task(task_id)
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage="SQL execution has already completed",
                data=StopExecuteSQLData(execute_task_id=task_id, stopped=False),
            )

        task.cancel()
        logger.info(f"Cancellation requested for SQL execution task: {task_id}")
        return Result(
            success=True,
            data=StopExecuteSQLData(execute_task_id=task_id, stopped=True),
        )

    def execute_context(
        self,
        context_type: str,
        request: ExecuteContextInput,
        agent_config: Optional[AgentConfig] = None,
    ) -> Result[ExecuteContextData]:
        """
        Execute context command.

        Args:
            context_type: Type of context command
            request: Context execution request

        Returns:
            ExecuteContextResult with context result
        """
        connector = self.current_db_connector
        current_db_name = self.current_db_name
        active_agent_config = agent_config or self.agent_config
        active_datasource = getattr(agent_config, "current_datasource", None) if agent_config is not None else None
        if not active_datasource:
            active_datasource = self.current_datasource
        cleanup_connector: Optional[Callable[[], None]] = None
        try:
            if agent_config is not None:
                connector, current_db_name, cleanup_connector = self._execution_connector(agent_config)
            active_catalog = getattr(connector, "catalog_name", None) or (
                getattr(self.cli_context, "current_catalog", None) if self.cli_context else None
            )
            active_schema = getattr(connector, "schema_name", None) or (
                getattr(self.cli_context, "current_schema", None) if self.cli_context else None
            )

            result_data = ContextResultData()

            if context_type == "tables":
                # Get tables list
                if connector:
                    tables = self._filter_table_names_by_grant(
                        connector.get_tables(),
                        connector,
                        agent_config,
                    )
                    if tables:
                        table_info_list = []
                        for table in tables:
                            table_info = TableInfo(
                                table_name=table,
                                table_type="table",
                                row_count=None,  # Would need additional query
                                columns_count=None,  # Would need additional query
                            )
                            table_info_list.append(table_info)
                        result_data.tables = table_info_list
                        result_data.total_count = len(table_info_list)
                else:
                    result_data.tables = []
                    result_data.total_count = 0

            elif context_type == "catalogs":
                # Get real catalogs from database connection
                if connector:
                    try:
                        # Try to get actual catalogs from the database
                        catalogs = connector.get_catalogs() if hasattr(connector, "get_catalogs") else ["main"]
                        current_catalog = active_catalog or "main"
                        result_data.context_info = {
                            "catalogs": catalogs,
                            "current": current_catalog,
                            "total_count": len(catalogs),
                        }
                    except Exception as e:
                        logger.debug(f"Failed to get catalogs from database: {e}")
                        result_data.context_info = {
                            "catalogs": ["main"],
                            "current": "main",
                            "error": str(e),
                        }
                else:
                    result_data.context_info = {
                        "catalogs": [],
                        "current": None,
                        "error": "No database connection",
                    }

            elif context_type == "context":
                # Get real current context with more details
                db_info = {}
                if connector:
                    try:
                        # Get database type and details
                        db_type = getattr(connector, "db_type", "unknown")
                        db_name = getattr(
                            connector,
                            "database_name",
                            current_db_name,
                        )
                        host = getattr(connector, "host", None)
                        port = getattr(connector, "port", None)

                        db_info = {
                            "db_type": db_type,
                            "database_name": db_name,
                            "host": host,
                            "port": port,
                            "connection_status": "connected",
                        }
                    except Exception as e:
                        logger.debug(f"Failed to get database details: {e}")
                        db_info = {
                            "database_name": current_db_name,
                            "connection_status": "connected",
                            "error": str(e),
                        }
                else:
                    db_info = {"connection_status": "disconnected"}

                result_data.context_info = {
                    "current_datasource": active_datasource,
                    "current_database": current_db_name,
                    "current_catalog": active_catalog,
                    "current_schema": active_schema,
                    "database": db_info,
                    "timestamp": now_utc_iso(),
                }

            elif context_type == "catalog":
                # Display database catalogs (@catalog command) - real implementation
                try:
                    if connector and active_agent_config:
                        # Use real catalog context similar to ContextCommands.cmd_catalog
                        db_type = getattr(active_agent_config, "db_type", "unknown")
                        catalog_name = active_catalog or "main"

                        result_data.context_info = {
                            "db_type": db_type,
                            "catalog_name": catalog_name,
                            "database_name": current_db_name,
                            "connection_status": "connected",
                            "message": "Database catalog context displayed",
                            "tables_available": len(connector.get_tables()) if connector else 0,
                        }
                    else:
                        result_data.context_info = {
                            "error": "No database connection or configuration available",
                            "message": "Catalog context not available",
                        }
                except Exception as e:
                    logger.error(f"Error getting catalog context: {e}")
                    result_data.context_info = {
                        "error": str(e),
                        "message": "Failed to get catalog context",
                    }

            elif context_type == "subject":
                # Display metrics (@subject command) - real implementation
                try:
                    # Check if agent_config is available for RAG functionality
                    if not active_agent_config:
                        result_data.context_info = {
                            "database_name": current_db_name,
                            "metrics_available": False,
                            "error": "No agent configuration available",
                            "message": "Metrics context not available - agent config required",
                        }
                    else:
                        # Use real metrics RAG similar to ContextCommands.cmd_subject
                        from datus.storage.metric.store import MetricRAG

                        metrics_rag = MetricRAG(active_agent_config)
                        metrics_count = metrics_rag.get_metrics_size()
                        rag_path = active_agent_config.rag_storage_path()

                        result_data.context_info = {
                            "database_name": current_db_name,
                            "metrics_available": metrics_count > 0,
                            "metrics_count": metrics_count,
                            "rag_storage_path": rag_path,
                            "message": f"Subject/metrics context displayed - {metrics_count} metrics found",
                        }
                except Exception as e:
                    logger.error(f"Error getting metrics context: {e}")
                    result_data.context_info = {
                        "database_name": current_db_name,
                        "metrics_available": False,
                        "error": str(e),
                        "message": "Failed to get metrics context",
                    }

            elif context_type == "sql":
                # Display historical SQL (@sql command) - real implementation
                try:
                    # Check if agent_config is available for RAG functionality
                    if not active_agent_config:
                        result_data.context_info = {
                            "database_name": current_db_name,
                            "historical_sql_available": False,
                            "error": "No agent configuration available",
                            "message": "SQL history context not available - agent config required",
                        }
                    else:
                        # Use real reference SQL RAG
                        from datus.storage.reference_sql.store import ReferenceSqlRAG

                        sql_rag = ReferenceSqlRAG(active_agent_config)
                        sql_count = sql_rag.get_reference_sql_size()
                        rag_path = active_agent_config.rag_storage_path()

                        result_data.context_info = {
                            "database_name": current_db_name,
                            "historical_sql_available": sql_count > 0,
                            "sql_count": sql_count,
                            "rag_storage_path": rag_path,
                            "message": f"Historical SQL context displayed - {sql_count} queries found",
                        }
                except Exception as e:
                    logger.error(f"Error getting SQL history context: {e}")
                    result_data.context_info = {
                        "database_name": current_db_name,
                        "historical_sql_available": False,
                        "error": str(e),
                        "message": "Failed to get SQL history context",
                    }

            else:
                return Result(
                    success=False,
                    errorCode=ErrorCode.CONTEXT_COMMAND_ERROR,
                    errorMessage=f"Context type '{context_type}' not supported",
                )

            data = ExecuteContextData(
                context_type=context_type,
                database_name=request.database_name or current_db_name,
                schema_name=request.schema_name,
                result=result_data,
            )

            return Result(success=True, data=data)

        except Exception as e:
            logger.error(f"Failed to execute context command: {e}")
            return Result(
                success=False,
                errorCode=ErrorCode.CONTEXT_COMMAND_ERROR,
                errorMessage=str(e),
            )
        finally:
            if cleanup_connector:
                cleanup_connector()

    def execute_internal_command(
        self,
        command: str,
        request: InternalCommandInput,
        user_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> Result[InternalCommandData]:
        """
        Execute internal command.

        Args:
            command: Internal command name
            request: Internal command request

        Returns:
            InternalCommandResult with command result
        """
        active_db_manager = self.db_manager
        active_datasource = self.current_datasource
        active_connector = self.current_db_connector
        cleanup_connector: Optional[Callable[[], None]] = None
        try:
            if agent_config is not None:
                active_db_manager, cleanup_connector = self._request_scoped_db_manager(agent_config.datasource_configs)
                active_datasource = getattr(agent_config, "current_datasource", None)
                if active_db_manager and active_datasource:
                    _, active_connector = active_db_manager.first_conn_with_name(active_datasource)

            result_data = InternalCommandResultData(command_output="", action_taken="none", context_changed=False)

            if command == "help":
                result_data.command_output = "Available commands: help, databases, tables, schemas, clear, exit"
                result_data.action_taken = "display_help"

            elif command in ["databases", "database"]:
                if active_db_manager:
                    connections = active_db_manager.get_connections(active_datasource)
                    # Handle both single connector and dict of connectors
                    if isinstance(connections, dict):
                        db_list = list(connections.keys())
                    else:
                        # Single connector - get database name from current context or config
                        db_list = [self.current_db_name] if self.current_db_name else ["default"]
                    db_list = self._filter_database_names_by_grant(db_list, agent_config)
                    result_data.command_output = f"Available databases: {', '.join(db_list)}"
                    result_data.data = {"databases": db_list}
                else:
                    result_data.command_output = "No database connections available"
                result_data.action_taken = "list_databases"

            elif command == "tables":
                if active_connector:
                    tables = self._filter_table_names_by_grant(
                        active_connector.get_tables(),
                        active_connector,
                        agent_config,
                    )
                    result_data.command_output = f"Tables: {', '.join(tables or [])}"
                    result_data.data = {"tables": tables or []}
                else:
                    result_data.command_output = "No database connection"
                result_data.action_taken = "list_tables"

            elif command == "clear":
                # Clear LLM-level session by service session ID
                # Args: service_session_id (finds and deletes corresponding LLM session)
                try:
                    service_session_id = request.args.strip() if request.args else None

                    if service_session_id:
                        # Call chat_service to delete LLM session for this service session
                        result = self.chat_service.delete_session(service_session_id, user_id=user_id)

                        if result.success:
                            result_data.command_output = f"Session {service_session_id} cleared successfully"
                            result_data.context_changed = True
                            result_data.data = {
                                "service_session_id": service_session_id,
                                "cleared": True,
                            }
                        else:
                            result_data.command_output = (
                                f"Failed to clear session {service_session_id}: "
                                f"{result.errorMessage or 'Unknown error'}"
                            )
                            result_data.data = {
                                "service_session_id": service_session_id,
                                "cleared": False,
                                "error": result.errorMessage,
                            }
                    else:
                        result_data.command_output = "No service session ID provided. Usage: clear <service_session_id>"
                        result_data.data = {"error": "Missing service_session_id parameter"}

                    result_data.action_taken = "clear_llm_session"

                except Exception as e:
                    logger.error(f"Error clearing LLM session: {e}")
                    result_data.command_output = f"Error clearing LLM session: {str(e)}"
                    result_data.action_taken = "clear_llm_session_error"
                    result_data.data = {"error": str(e)}

            elif command in ["exit", "quit"]:
                result_data.command_output = "Goodbye!"
                result_data.action_taken = "exit_program"

            elif command == "chat_info":
                # Real chat info implementation based on ChatCommands.cmd_chat_info
                try:
                    # Try to get session info from current context or session manager
                    current_session_id = getattr(self, "current_session_id", None)

                    if current_session_id:
                        session_info_result = (
                            self.chat_service.get_session_info(current_session_id, user_id=user_id)
                            if self.chat_service
                            else None
                        )
                        session_info = (
                            session_info_result.data
                            if session_info_result and session_info_result.success and session_info_result.data
                            else None
                        )

                        if session_info and session_info.get("exists", False):
                            result_data.command_output = (
                                f"Current session: {current_session_id}\n"
                                f"  Token Count: {session_info.get('total_tokens', 0)}\n"
                                f"  Action Count: {session_info.get('action_count', 0)}\n"
                                f"  Created: {session_info.get('created_at', 'Unknown')}\n"
                                f"  Last Updated: {session_info.get('last_updated', 'Unknown')}"
                            )
                            result_data.data = {
                                "current_session_id": current_session_id,
                                "session_info": session_info,
                                "token_count": session_info.get("total_tokens", 0),
                                "action_count": session_info.get("action_count", 0),
                                "created_at": session_info.get("created_at"),
                                "last_updated": session_info.get("last_updated"),
                            }
                        else:
                            result_data.command_output = f"Session {current_session_id} info not available"
                            result_data.data = {
                                "current_session_id": current_session_id,
                                "error": "Session info not found",
                            }
                    else:
                        result_data.command_output = "No active session"
                        result_data.data = {"current_session_id": None}

                    result_data.action_taken = "show_chat_info"

                except Exception as e:
                    logger.error(f"Error getting chat info: {e}")
                    result_data.command_output = f"Error getting chat info: {str(e)}"
                    result_data.data = {"current_session_id": None, "error": str(e)}
                    result_data.action_taken = "show_chat_info_error"

            elif command == "sessions":
                # Use chat_service.list_sessions() for consistent session listing
                try:
                    sessions_result = self.chat_service.list_sessions(user_id=user_id)

                    if not sessions_result.success:
                        result_data.command_output = (
                            f"Error listing sessions: {sessions_result.errorMessage or 'Unknown error'}"
                        )
                        result_data.data = {
                            "sessions": [],
                            "error": sessions_result.errorMessage,
                        }
                        result_data.action_taken = "list_sessions_error"
                    elif not sessions_result.data:
                        result_data.command_output = "No chat sessions found"
                        result_data.data = {"sessions": []}
                        result_data.action_taken = "list_sessions"
                    else:
                        # Convert ChatSessionData to dict format
                        sessions_with_info = []
                        for session_data in sessions_result.data.sessions:
                            # Format timestamps to be readable
                            created = session_data.created_at
                            updated = session_data.last_updated
                            if isinstance(created, str) and len(created) > 19:
                                created = created[:19]
                            if isinstance(updated, str) and len(updated) > 19:
                                updated = updated[:19]

                            session_info = {
                                "session_id": session_data.session_id,
                                "created_at": created,
                                "last_updated": updated,
                                "total_turns": session_data.total_turns,
                                "token_count": session_data.token_count,
                                "is_active": session_data.is_active,
                            }
                            sessions_with_info.append(session_info)

                        session_list = [s["session_id"] for s in sessions_with_info]
                        result_data.command_output = f"Available sessions: {', '.join(session_list[:5])}"
                        if len(session_list) > 5:
                            result_data.command_output += f" ... and {len(session_list) - 5} more"

                        result_data.data = {
                            "sessions": sessions_with_info,
                            "total_count": sessions_result.data.total_count,
                        }
                        result_data.action_taken = "list_sessions"

                except Exception as e:
                    logger.error(f"Error listing sessions: {e}")
                    result_data.command_output = f"Error listing sessions: {str(e)}"
                    result_data.data = {"sessions": [], "error": str(e)}
                    result_data.action_taken = "list_sessions_error"

            else:
                return Result(
                    success=False,
                    errorCode=ErrorCode.INTERNAL_COMMAND_ERROR,
                    errorMessage=f"Internal command '{command}' not supported",
                )

            data = InternalCommandData(command=command, args=request.args, result=result_data)

            return Result(success=True, data=data)

        except Exception as e:
            logger.error(f"Failed to execute internal command: {e}")
            return Result(
                success=False,
                errorCode=ErrorCode.INTERNAL_COMMAND_ERROR,
                errorMessage=str(e),
            )
        finally:
            if cleanup_connector:
                cleanup_connector()

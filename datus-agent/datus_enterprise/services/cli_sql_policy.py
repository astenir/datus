"""Datasource-grant helpers used by downstream SQL execution policy."""

import re
from fnmatch import fnmatchcase
from typing import Optional, Sequence

from datus.api.models.base_models import Result
from datus.api.models.cli_models import ExecuteSQLData
from datus.api.models.config_models import ErrorCode
from datus.configuration.agent_config_loader import AgentConfig
from datus.tools.func_tool.database import DBFuncTool
from datus.utils.constants import SQLType
from datus.utils.datasource_scope import datasource_field_order, datasource_scope_matches, grant_uses_tree_scope
from datus.utils.exceptions import DatusException
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def scope_patterns(grant: dict, scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    patterns = [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]
    return patterns or None


def compose_scope_tokens(
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


def schema_qualified_dialect(dialect: str) -> bool:
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


def catalog_qualified_dialect(dialect: str) -> bool:
    return (dialect or "").strip().lower() in {"starrocks"}


SHOW_NAMESPACE_RE = re.compile(
    r"^\s*SHOW\s+(?:FULL\s+)?(?P<kind>TABLES|VIEWS|DATABASES|SCHEMAS)\s+(?:FROM|IN)\s+(?P<target>[^\s;]+)",
    flags=re.IGNORECASE,
)
SHOW_TABLE_TARGET_RE = re.compile(
    r"^\s*SHOW\s+(?:FULL\s+)?(?:COLUMNS|FIELDS|INDEX|INDEXES|KEYS)\s+"
    r"(?:FROM|IN)\s+(?P<target>[^\s;]+)(?:\s+(?:FROM|IN)\s+(?P<namespace>[^\s;]+))?",
    flags=re.IGNORECASE,
)
SHOW_CREATE_TARGET_RE = re.compile(
    r"^\s*SHOW\s+CREATE\s+(?:TABLE|VIEW)\s+(?P<target>[^\s;]+)",
    flags=re.IGNORECASE,
)


def current_datasource_grant(agent_config: Optional[AgentConfig]) -> tuple[str, object | None]:
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


def field_order_for_grant(
    field_order: Sequence[str],
    agent_config: Optional[AgentConfig],
    *,
    dialect: str = "",
) -> Sequence[str]:
    order = list(field_order)
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return order

    has_catalog_scope = scope_patterns(grant, "catalogs") is not None
    has_database_scope = scope_patterns(grant, "databases") is not None
    has_schema_scope = scope_patterns(grant, "schemas") is not None
    if has_catalog_scope and "catalog" not in order:
        database_index = order.index("database") if "database" in order else len(order)
        table_index = order.index("table") if "table" in order else len(order)
        order.insert(min(database_index, table_index), "catalog")
    if has_catalog_scope and catalog_qualified_dialect(dialect) and "database" not in order:
        table_index = order.index("table") if "table" in order else len(order)
        order.insert(table_index, "database")
    if has_database_scope and "database" not in order:
        if schema_qualified_dialect(dialect) and "schema" in order:
            order.insert(order.index("schema"), "database")
        else:
            table_index = order.index("table") if "table" in order else len(order)
            order.insert(table_index, "database")
    if (has_schema_scope or (has_database_scope and schema_qualified_dialect(dialect))) and "schema" not in order:
        table_index = order.index("table") if "table" in order else len(order)
        order.insert(table_index, "schema")
    return order


def scoped_table_patterns(
    agent_config: Optional[AgentConfig],
    field_order: Optional[Sequence[str]] = None,
) -> Optional[list[str]]:
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return None

    table_patterns = scope_patterns(grant, "tables")
    schema_patterns = scope_patterns(grant, "schemas")
    database_patterns = scope_patterns(grant, "databases")
    catalog_patterns = scope_patterns(grant, "catalogs")
    if table_patterns is not None:
        if not table_patterns:
            return ["__NO_TABLES_ALLOWED__"]
        if catalog_patterns == []:
            return ["__NO_CATALOGS_ALLOWED__"]
        if database_patterns == []:
            return ["__NO_DATABASES_ALLOWED__"]
        if schema_patterns == []:
            return ["__NO_SCHEMAS_ALLOWED__"]
        return compose_scope_tokens(
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
        return compose_scope_tokens(
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
        return compose_scope_tokens(field_order, catalogs=catalog_patterns, databases=database_patterns)
    if catalog_patterns is not None:
        if not catalog_patterns:
            return ["__NO_CATALOGS_ALLOWED__"]
        return compose_scope_tokens(field_order, catalogs=catalog_patterns)
    return None


def metadata_scope_target(statement: str) -> str:
    match = SHOW_CREATE_TARGET_RE.match(statement)
    if match:
        return match.group("target").strip().strip(";")

    match = SHOW_TABLE_TARGET_RE.match(statement)
    if match:
        target = match.group("target").strip().strip(";")
        namespace = (match.group("namespace") or "").strip().strip(";")
        if namespace:
            if "." in target:
                return ""
            return f"{namespace}.{target}"
        return target

    match = SHOW_NAMESPACE_RE.match(statement)
    if not match:
        return ""
    target = match.group("target").strip().strip(";")
    if not target:
        return ""
    kind = match.group("kind").strip().upper()
    if kind in {"DATABASES", "SCHEMAS"}:
        return f"{target}.*.*"
    return f"{target}.*"


def metadata_scope_denial(
    sql: str,
    sql_type: SQLType,
    connector,
    agent_config: Optional[AgentConfig],
    guard: DBFuncTool,
) -> Optional[str]:
    if sql_type != SQLType.METADATA_SHOW:
        return None
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return None
    scoped_keys = ("catalogs", "databases", "schemas", "tables")
    if not any(scope_patterns(grant, key) is not None for key in scoped_keys):
        return None

    from datus.utils.sql_utils import _first_statement, extract_table_names

    dialect = getattr(connector, "dialect", "") or ""
    if extract_table_names(sql, dialect=dialect, ignore_empty=True):
        return None

    statement = _first_statement(sql).strip()
    target = metadata_scope_target(statement)
    if not target:
        return "Metadata SQL requires an authorized target under scoped datasource grants."

    coordinate = guard._build_table_coordinate(raw_name=target)
    if guard._table_matches_scope(coordinate):
        return None
    return f"Metadata SQL target is outside scoped context: {target}"


def database_grant_denial(
    agent_config: Optional[AgentConfig], database_name: Optional[str], connector=None
) -> Optional[str]:
    datasource, grant = current_datasource_grant(agent_config)
    if grant is True:
        return None
    if grant is None:
        return None
    if not isinstance(grant, dict):
        return f"Datasource '{datasource}' is not authorized for this request."

    patterns = scope_patterns(grant, "databases")
    if patterns is None:
        return None
    requested_database = (database_name or "").strip()
    if not requested_database:
        return None
    dialect = str(getattr(connector, "dialect", "") or "")
    field_order = field_order_for_grant(
        datasource_field_order(dialect),
        agent_config,
        dialect=dialect,
    )
    if "database" in field_order and grant_uses_tree_scope(grant, field_order):
        if datasource_scope_matches(
            grant,
            coordinate={"catalog": "", "database": requested_database, "schema": "", "table": ""},
            target_field="database",
            field_order=field_order,
        ):
            return None
    if patterns and any(fnmatchcase(requested_database, pattern) for pattern in patterns):
        return None
    return f"Requested database '{requested_database}' is not authorized for datasource '{datasource}'."


def filter_database_names_by_grant(database_names: Sequence[str], agent_config: Optional[AgentConfig]) -> list[str]:
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return list(database_names)

    patterns = scope_patterns(grant, "databases")
    if patterns is None:
        return list(database_names)
    if not patterns:
        return []
    return [
        database_name
        for database_name in database_names
        if any(fnmatchcase(database_name, pattern) for pattern in patterns)
    ]


def filter_catalog_names_by_grant(catalog_names: Sequence[str], agent_config: Optional[AgentConfig]) -> list[str]:
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return list(catalog_names)

    patterns = scope_patterns(grant, "catalogs")
    if patterns is None:
        return list(catalog_names)
    if not patterns:
        return []
    return [
        catalog_name
        for catalog_name in catalog_names
        if any(fnmatchcase(catalog_name, pattern) for pattern in patterns)
    ]


def filter_schema_names_by_grant(schema_names: Sequence[str], agent_config: Optional[AgentConfig]) -> list[str]:
    _datasource, grant = current_datasource_grant(agent_config)
    if not isinstance(grant, dict):
        return list(schema_names)

    patterns = scope_patterns(grant, "schemas")
    if patterns is None:
        return list(schema_names)
    if not patterns:
        return []
    return [
        schema_name for schema_name in schema_names if any(fnmatchcase(schema_name, pattern) for pattern in patterns)
    ]


def filter_table_names_by_grant(
    table_names: Sequence[str], connector, agent_config: Optional[AgentConfig]
) -> list[str]:
    guard = object.__new__(DBFuncTool)
    guard._primary_connector = connector
    guard.agent_config = agent_config
    principal = getattr(agent_config, "principal", {}) if agent_config else {}
    guard.principal = dict(principal) if isinstance(principal, dict) else {}
    guard._default_datasource = str(
        guard.principal.get("datasource") or getattr(agent_config, "current_datasource", "") or ""
    )
    guard.sub_agent_name = None
    guard._field_order = field_order_for_grant(
        guard._determine_field_order(),
        agent_config,
        dialect=getattr(connector, "dialect", "") or "",
    )
    scoped_tables = scoped_table_patterns(agent_config, guard._field_order)
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


def authorize_read_sql(sql: str, connector, agent_config: Optional[AgentConfig]) -> str | Result[ExecuteSQLData]:
    if bool(getattr(agent_config, "_business_datasource_read_only", False)):
        from datus.tools.business_datasource_policy import (
            business_datasource_read_only_message,
            evaluate_business_datasource_read_only_sql,
        )

        decision = evaluate_business_datasource_read_only_sql(
            sql,
            getattr(connector, "dialect", "") or "",
        )
        if not decision.allowed:
            return Result(
                success=False,
                errorCode=ErrorCode.SQL_EXECUTION_ERROR,
                errorMessage=business_datasource_read_only_message(decision.operation),
            )

    guard = object.__new__(DBFuncTool)
    guard._primary_connector = connector
    guard.agent_config = agent_config
    # This lightweight authorization guard deliberately bypasses DBFuncTool.__init__.
    # Enterprise request-level read-only enforcement already ran above; initialize
    # the tool-layer flags explicitly so the shared validator keeps working for
    # normal projected configs and test doubles.
    guard.enterprise_read_only = False
    guard.read_only = False
    principal = getattr(agent_config, "principal", {}) if agent_config is not None else {}
    guard.principal = dict(principal) if isinstance(principal, dict) else {}
    guard.sub_agent_name = None
    guard._field_order = field_order_for_grant(
        guard._determine_field_order(),
        agent_config,
        dialect=getattr(connector, "dialect", "") or "",
    )
    scoped_tables = scoped_table_patterns(agent_config, guard._field_order)
    guard._scoped_patterns = guard._load_scoped_patterns(scoped_tables)

    validation_error, sql_type = guard._validate_read_sql(sql, connector)
    if validation_error:
        return Result(
            success=False,
            errorCode=ErrorCode.SQL_EXECUTION_ERROR,
            errorMessage=validation_error.error,
        )
    metadata_denial = metadata_scope_denial(sql, sql_type, connector, agent_config, guard)
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
    metadata_denial = metadata_scope_denial(
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


def authorize_dashboard_read_sql(
    sql: str,
    connector,
    agent_config: Optional[AgentConfig],
    *,
    dashboard_slug: str,
    query_slug: str,
) -> str | Result:
    try:
        authorized_sql = authorize_read_sql(sql, connector, agent_config)
    except Exception as exc:
        logger.exception("Dashboard SQL authorization failed for %s/%s: %s", dashboard_slug, query_slug, exc)
        return Result(
            success=False,
            errorCode="QUERY_EXECUTION_FAILED",
            errorMessage="SQL authorization failed",
        )
    if isinstance(authorized_sql, str):
        return authorized_sql
    return Result(
        success=False,
        errorCode="QUERY_EXECUTION_FAILED",
        errorMessage=authorized_sql.errorMessage,
    )

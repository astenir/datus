# Oracle Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-shaped `datus-oracle` adapter package for Oracle Database, registered as `type: oracle`, with SQL execution, metadata discovery, DDL retrieval, URI/context helpers, tests, and documentation.

**Architecture:** Implement Oracle as a SQLAlchemy-based adapter that inherits from `datus_sqlalchemy.SQLAlchemyConnector`, matching the MySQL/PostgreSQL package layout. Oracle has schema/user-level namespaces rather than PostgreSQL-style databases, so `database_name` maps to Oracle service/SID only for connection construction and `schema_name` maps to Oracle owner/user for object discovery and qualification.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy 2.x, `oracledb`, pytest, uv workspace packaging.

---

## File Structure

- Create: `datus-oracle/pyproject.toml` - package metadata, dependencies, entry point.
- Create: `datus-oracle/README.md` - install, config, usage, testing notes.
- Create: `datus-oracle/datus_oracle/__init__.py` - exports and adapter registration.
- Create: `datus-oracle/datus_oracle/config.py` - Pydantic config for host/port/username/password/service/SID/schema.
- Create: `datus-oracle/datus_oracle/handlers.py` - SQLAlchemy URI builder and Datus context resolver.
- Create: `datus-oracle/datus_oracle/connector.py` - Oracle connector behavior and metadata queries.
- Create: `datus-oracle/tests/__init__.py` - test package marker.
- Create: `datus-oracle/tests/conftest.py` - shared pytest path setup if needed.
- Create: `datus-oracle/tests/unit/__init__.py` - unit test marker.
- Create: `datus-oracle/tests/unit/test_config.py` - config validation tests.
- Create: `datus-oracle/tests/unit/test_handlers.py` - URI/context tests.
- Create: `datus-oracle/tests/unit/test_connector_unit.py` - connector behavior tests with mocks.
- Create: `datus-oracle/tests/integration/__init__.py` - integration test marker.
- Create: `datus-oracle/tests/integration/conftest.py` - optional Oracle connection fixtures gated by env vars.
- Create: `datus-oracle/tests/integration/test_connection.py` - real Oracle connection smoke tests, skipped by default.
- Modify: `pyproject.toml` - add `datus-oracle` to workspace members and `known-first-party`.
- Modify: `README.md` - add Oracle to the implemented adapters list.

## Namespacing Decisions

- `OracleConfig.service_name`: preferred Oracle network service name.
- `OracleConfig.sid`: optional legacy SID alternative.
- `OracleConfig.database`: accepted alias for `service_name` to fit existing Datus config conventions.
- `OracleConfig.schema_name`: default object owner/schema. Defaults to `username.upper()` when omitted.
- `get_databases()`: returns service-level logical database as a single-item list when configured; Oracle does not expose peer databases through one connection.
- `get_schemas()`: returns Oracle users from `ALL_USERS`, filtered to remove common system schemas.
- `full_name(schema_name, table_name)`: returns `"SCHEMA"."TABLE"`; no service/database qualification.
- `get_tables()`, `get_views()`, `get_materialized_views()`: query `ALL_TABLES`, `ALL_VIEWS`, and `ALL_MVIEWS`.
- `get_schema()`: query `ALL_TAB_COLUMNS`, `ALL_COL_COMMENTS`, and primary-key constraints.
- `get_tables_with_ddl()` and `get_views_with_ddl()`: call `DBMS_METADATA.GET_DDL`; return a readable fallback comment when privileges are missing.

---

### Task 1: Package Skeleton and Workspace Registration

**Files:**
- Create: `datus-oracle/pyproject.toml`
- Create: `datus-oracle/datus_oracle/__init__.py`
- Create: `datus-oracle/datus_oracle/config.py`
- Create: `datus-oracle/tests/__init__.py`
- Create: `datus-oracle/tests/unit/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing import/package tests**

Create `datus-oracle/tests/unit/test_config.py` with:

```python
import pytest
from pydantic import ValidationError

from datus_oracle import OracleConfig


def test_config_defaults_to_service_name_and_username_schema():
    config = OracleConfig(username="app_user")

    assert config.host == "127.0.0.1"
    assert config.port == 1521
    assert config.username == "app_user"
    assert config.password == ""
    assert config.service_name == "FREEPDB1"
    assert config.sid is None
    assert config.database == "FREEPDB1"
    assert config.schema_name == "APP_USER"
    assert config.timeout_seconds == 30


def test_config_accepts_database_alias_for_service_name():
    config = OracleConfig(username="app", database="ORCLPDB1")

    assert config.service_name == "ORCLPDB1"
    assert config.database == "ORCLPDB1"


def test_config_prefers_explicit_service_name_over_database_alias():
    config = OracleConfig(username="app", database="ignored", service_name="SALES")

    assert config.service_name == "SALES"
    assert config.database == "SALES"


def test_config_accepts_schema_alias():
    config = OracleConfig(username="app", schema="reporting")

    assert config.schema_name == "REPORTING"


def test_config_forbids_service_name_and_sid_together():
    with pytest.raises(ValidationError) as exc_info:
        OracleConfig(username="app", service_name="FREEPDB1", sid="XE")

    assert any(error["type"] == "value_error" for error in exc_info.value.errors())


def test_config_forbids_extra_fields():
    with pytest.raises(ValidationError) as exc_info:
        OracleConfig(username="app", extra_field="nope")

    assert any(error["type"] == "extra_forbidden" for error in exc_info.value.errors())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_config.py -v
```

Expected: FAIL because `datus_oracle` does not exist.

- [ ] **Step 3: Add minimal package files**

Create `datus-oracle/datus_oracle/config.py`:

```python
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OracleConfig(BaseModel):
    """Oracle-specific configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(default="127.0.0.1", description="Oracle server host")
    port: int = Field(default=1521, description="Oracle listener port")
    username: str = Field(..., description="Oracle username")
    password: str = Field(default="", description="Oracle password", json_schema_extra={"input_type": "password"})
    service_name: Optional[str] = Field(default=None, alias="database", description="Oracle service name")
    sid: Optional[str] = Field(default=None, description="Oracle SID; mutually exclusive with service_name")
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Default Oracle schema/owner")
    thick_mode: bool = Field(default=False, description="Use python-oracledb thick mode")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @model_validator(mode="after")
    def normalize_oracle_names(self):
        if self.service_name and self.sid:
            raise ValueError("service_name/database and sid are mutually exclusive")
        if not self.service_name and not self.sid:
            self.service_name = "FREEPDB1"
        if not self.schema_name:
            self.schema_name = self.username.upper()
        else:
            self.schema_name = self.schema_name.upper()
        return self

    @property
    def database(self) -> str:
        return self.service_name or self.sid or ""
```

Create `datus-oracle/datus_oracle/__init__.py`:

```python
from .config import OracleConfig

__version__ = "0.1.0"
__all__ = ["OracleConfig", "register"]


def register():
    """Register Oracle connector with Datus registry."""
    from datus_db_core import connector_registry

    from .connector import OracleConnector
    from .handlers import build_oracle_uri, resolve_oracle_context

    connector_registry.register(
        "oracle",
        OracleConnector,
        config_class=OracleConfig,
        capabilities={"schema"},
        uri_builder=build_oracle_uri,
        context_resolver=resolve_oracle_context,
    )
```

Create `datus-oracle/pyproject.toml`:

```toml
[project]
name = "datus-oracle"
version = "0.1.0"
description = "Oracle database adapter for Datus"
requires-python = ">=3.12"
license = {file = "../LICENSE"}
keywords = ["datus", "database", "oracle", "adapter"]
dependencies = [
    "datus-db-core>=0.1.0",
    "datus-sqlalchemy>=0.1.6",
    "oracledb>=2.0.0",
]

[project.entry-points."datus.adapters"]
oracle = "datus_oracle:register"

[tool.uv.sources]
datus-db-core = { workspace = true }
datus-sqlalchemy = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["datus_oracle"]
```

Modify root `pyproject.toml`:

```toml
members = ["datus-db-core", "datus-mysql", "datus-postgresql", "datus-sqlalchemy", "datus-starrocks", "datus-snowflake", "datus-clickzetta", "datus-clickhouse", "datus-hive", "datus-redshift", "datus-spark", "datus-trino", "datus-greenplum", "datus-oracle"]
```

Also append `datus_oracle` to `known-first-party`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml datus-oracle
git commit -m "feat: scaffold oracle adapter package"
```

---

### Task 2: URI Builder and Context Resolver

**Files:**
- Create: `datus-oracle/datus_oracle/handlers.py`
- Create: `datus-oracle/tests/unit/test_handlers.py`

- [ ] **Step 1: Write failing handler tests**

Create `datus-oracle/tests/unit/test_handlers.py`:

```python
from datus_oracle import OracleConfig
from datus_oracle.handlers import build_oracle_uri, resolve_oracle_context


def test_build_oracle_uri_with_service_name():
    config = OracleConfig(
        host="db.example.com",
        port=1522,
        username="app",
        password="p@ss word",
        service_name="SALES",
    )

    uri = build_oracle_uri(config)

    assert uri.startswith("oracle+oracledb://app:p%40ss+word@db.example.com:1522/")
    assert "service_name=SALES" in uri


def test_build_oracle_uri_with_sid():
    config = OracleConfig(username="app", sid="XE", service_name=None)

    uri = build_oracle_uri(config)

    assert "sid=XE" in uri
    assert "service_name" not in uri


def test_resolve_oracle_context_prefers_query_schema():
    config = OracleConfig(username="app", service_name="FREEPDB1", schema="APP")
    uri = "oracle+oracledb://app:secret@localhost:1521/?service_name=FREEPDB1&schema=reporting"

    dialect, catalog, database, schema = resolve_oracle_context(config, uri)

    assert dialect == "oracle"
    assert catalog == ""
    assert database == "FREEPDB1"
    assert schema == "REPORTING"


def test_resolve_oracle_context_uses_sid_as_database_when_no_service_name():
    config = OracleConfig(username="app", sid="XE", service_name=None)
    uri = "oracle+oracledb://app:secret@localhost:1521/?sid=XE"

    assert resolve_oracle_context(config, uri) == ("oracle", "", "XE", "APP")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_handlers.py -v
```

Expected: FAIL because `handlers.py` does not exist.

- [ ] **Step 3: Implement handlers**

Create `datus-oracle/datus_oracle/handlers.py`:

```python
from typing import Dict, Optional, Tuple, Union

from sqlalchemy.engine.url import URL, make_url


def _clean_str(value: Optional[Union[str, int]]) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if item:
                return str(item).strip()
        return ""
    return str(value).strip()


def _value_or_none(value: Optional[Union[str, int]]) -> Optional[str]:
    cleaned = _clean_str(value)
    return cleaned or None


def _port_or_none(port_value: Optional[Union[str, int]]) -> Optional[int]:
    cleaned = _clean_str(port_value)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _upper_or_none(value: Optional[Union[str, int]]) -> Optional[str]:
    cleaned = _clean_str(value)
    return cleaned.upper() if cleaned else None


def build_oracle_uri(db_config) -> str:
    query: Dict[str, str] = {}
    service_name = _value_or_none(getattr(db_config, "service_name", None) or getattr(db_config, "database", None))
    sid = _value_or_none(getattr(db_config, "sid", None))
    schema = _upper_or_none(getattr(db_config, "schema_name", None) or getattr(db_config, "schema", None))
    if service_name:
        query["service_name"] = service_name
    elif sid:
        query["sid"] = sid
    if schema:
        query["schema"] = schema
    return str(
        URL.create(
            drivername="oracle+oracledb",
            username=_value_or_none(db_config.username),
            password=_value_or_none(db_config.password),
            host=_value_or_none(db_config.host),
            port=_port_or_none(db_config.port),
            database=None,
            query=query,
        )
    )


def resolve_oracle_context(db_config, uri: str) -> Tuple[str, str, str, str]:
    url = make_url(uri)
    query_params: Dict[str, str] = {k: _clean_str(v) for k, v in url.query.items()}
    service_name = query_params.get("service_name") or _clean_str(getattr(db_config, "service_name", None))
    sid = query_params.get("sid") or _clean_str(getattr(db_config, "sid", None))
    database = service_name or sid or _clean_str(getattr(db_config, "database", None))
    schema = (
        _upper_or_none(query_params.get("schema"))
        or _upper_or_none(getattr(db_config, "schema_name", None))
        or _upper_or_none(getattr(db_config, "schema", None))
        or _upper_or_none(getattr(db_config, "username", None))
        or ""
    )
    return "oracle", "", database, schema
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_handlers.py datus-oracle/tests/unit/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datus-oracle/datus_oracle/handlers.py datus-oracle/tests/unit/test_handlers.py datus-oracle/tests/unit/test_config.py
git commit -m "feat: add oracle uri and context handlers"
```

---

### Task 3: Connector Initialization and Identifier Behavior

**Files:**
- Create: `datus-oracle/datus_oracle/connector.py`
- Modify: `datus-oracle/datus_oracle/__init__.py`
- Create: `datus-oracle/tests/unit/test_connector_unit.py`

- [ ] **Step 1: Write failing connector initialization tests**

Create `datus-oracle/tests/unit/test_connector_unit.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from datus_oracle import OracleConfig, OracleConnector


def test_connector_initialization_with_config_object():
    config = OracleConfig(username="app", password="secret", service_name="FREEPDB1", schema="reporting")

    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None) as mock_init:
        connector = OracleConnector(config)

    assert connector.config == config
    assert connector.host == "127.0.0.1"
    assert connector.port == 1521
    assert connector.username == "app"
    assert connector.password == "secret"
    assert connector.database_name == "FREEPDB1"
    assert connector.schema_name == "REPORTING"
    mock_init.assert_called_once()
    assert mock_init.call_args.kwargs["dialect"] == "oracle"


def test_connector_initialization_with_dict():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector({"username": "app", "sid": "XE", "service_name": None})

    assert connector.database_name == "XE"
    assert connector.schema_name == "APP"


def test_connector_initialization_invalid_type():
    with pytest.raises(TypeError, match="config must be OracleConfig or dict"):
        OracleConnector("invalid")


def test_connection_string_uses_service_name_query():
    config = OracleConfig(host="db.example.com", port=1522, username="app", password="p@ss", service_name="SALES")

    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__") as mock_init:
        OracleConnector(config)

    connection_string = mock_init.call_args.args[0]
    assert connection_string.startswith("oracle+oracledb://app:p%40ss@db.example.com:1522/")
    assert "service_name=SALES" in connection_string


def test_quote_identifier_uses_ansi_double_quotes():
    assert OracleConnector.quote_identifier(MagicMock(), "table_name") == '"table_name"'


def test_quote_identifier_escapes_double_quotes():
    assert OracleConnector.quote_identifier(MagicMock(), 'a"b') == '"a""b"'


def test_full_name_uses_schema_and_table_only():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector(OracleConfig(username="app", schema="sales"))

    assert connector.full_name(schema_name="HR", table_name="EMP") == '"HR"."EMP"'
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py -v
```

Expected: FAIL because `OracleConnector` is not exported or `connector.py` is missing.

- [ ] **Step 3: Implement connector initialization and naming**

Create `datus-oracle/datus_oracle/connector.py`:

```python
from typing import Any, Dict, List, Optional, Set, Union, override

from sqlalchemy import text

from datus_db_core import TABLE_TYPE, DatusDbException, ErrorCode, MigrationTargetMixin, get_logger
from datus_sqlalchemy import SQLAlchemyConnector

from .config import OracleConfig
from .handlers import build_oracle_uri

logger = get_logger(__name__)


class OracleConnector(SQLAlchemyConnector, MigrationTargetMixin):
    """Oracle database connector."""

    def __init__(self, config: Union[OracleConfig, dict]):
        if isinstance(config, dict):
            config = OracleConfig(**config)
        elif not isinstance(config, OracleConfig):
            raise TypeError(f"config must be OracleConfig or dict, got {type(config)}")

        self.config = config
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        database = config.database
        schema = config.schema_name or config.username.upper()

        super().__init__(
            build_oracle_uri(config),
            dialect="oracle",
            timeout_seconds=config.timeout_seconds,
        )
        self.config = config
        self._default_database = database
        self._default_schema = schema

    @override
    def _sys_databases(self) -> Set[str]:
        return set()

    @override
    def _sys_schemas(self) -> Set[str]:
        return {
            "SYS",
            "SYSTEM",
            "OUTLN",
            "DBSNMP",
            "APPQOSSYS",
            "AUDSYS",
            "CTXSYS",
            "GSMADMIN_INTERNAL",
            "MDSYS",
            "OJVMSYS",
            "ORDDATA",
            "ORDSYS",
            "XDB",
            "WMSYS",
        }

    @override
    def quote_identifier(self, name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @override
    def full_name(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        schema_name = schema_name or self.schema_name
        if schema_name:
            return f"{self.quote_identifier(schema_name)}.{self.quote_identifier(table_name)}"
        return self.quote_identifier(table_name)
```

Modify `datus-oracle/datus_oracle/__init__.py`:

```python
from .config import OracleConfig
from .connector import OracleConnector

__version__ = "0.1.0"
__all__ = ["OracleConnector", "OracleConfig", "register"]
```

Keep the existing `register()` body.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py datus-oracle/tests/unit/test_handlers.py datus-oracle/tests/unit/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datus-oracle/datus_oracle datus-oracle/tests/unit/test_connector_unit.py
git commit -m "feat: add oracle connector initialization"
```

---

### Task 4: Oracle Metadata Discovery

**Files:**
- Modify: `datus-oracle/datus_oracle/connector.py`
- Modify: `datus-oracle/tests/unit/test_connector_unit.py`

- [ ] **Step 1: Write failing metadata tests**

Append to `datus-oracle/tests/unit/test_connector_unit.py`:

```python
def make_connector():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector(OracleConfig(username="app", service_name="FREEPDB1", schema="APP"))
    connector.connect = MagicMock()
    connector.database_name = "FREEPDB1"
    connector.schema_name = "APP"
    return connector


def test_get_tables_queries_all_tables_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock()
    connector._execute_pandas.return_value = {"OWNER": ["APP"], "TABLE_NAME": ["CUSTOMERS"]}

    assert connector.get_tables(schema_name="APP") == ["CUSTOMERS"]
    sql = connector._execute_pandas.call_args.args[0]
    assert "FROM ALL_TABLES" in sql
    assert "OWNER = 'APP'" in sql
    assert "DROPPED = 'NO'" in sql


def test_get_views_queries_all_views_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value={"OWNER": ["APP"], "VIEW_NAME": ["ACTIVE_CUSTOMERS"]})

    assert connector.get_views(schema_name="APP") == ["ACTIVE_CUSTOMERS"]
    assert "FROM ALL_VIEWS" in connector._execute_pandas.call_args.args[0]


def test_get_materialized_views_queries_all_mviews_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value={"OWNER": ["APP"], "MVIEW_NAME": ["CUSTOMER_SUMMARY"]})

    assert connector.get_materialized_views(schema_name="APP") == ["CUSTOMER_SUMMARY"]
    assert "FROM ALL_MVIEWS" in connector._execute_pandas.call_args.args[0]


def test_get_schemas_filters_system_schemas():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value={"USERNAME": ["SYS", "APP", "REPORTING"]})

    assert connector.get_schemas() == ["APP", "REPORTING"]


def test_get_databases_returns_configured_service_name():
    connector = make_connector()

    assert connector.get_databases() == ["FREEPDB1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py -v
```

Expected: FAIL because metadata methods are missing or inherited generic behavior is wrong for Oracle.

- [ ] **Step 3: Implement metadata methods**

Add to `OracleConnector`:

```python
    def _owner_filter(self, schema_name: str = "") -> str:
        owner = (schema_name or self.schema_name or self.username).upper().replace("'", "''")
        return f"OWNER = '{owner}'"

    def _frame_rows(self, query_result, *columns: str) -> List[Dict[str, Any]]:
        rows = []
        if hasattr(query_result, "empty"):
            if query_result.empty:
                return rows
            for _, row in query_result.iterrows():
                rows.append({column: row[column] for column in columns})
            return rows
        count = len(query_result[columns[0]]) if columns and columns[0] in query_result else 0
        for i in range(count):
            rows.append({column: query_result[column][i] for column in columns})
        return rows

    def _get_metadata(
        self,
        table_type: TABLE_TYPE = "table",
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[Dict[str, str]]:
        self.connect()
        object_sql = {
            "table": ("ALL_TABLES", "TABLE_NAME", "DROPPED = 'NO'"),
            "view": ("ALL_VIEWS", "VIEW_NAME", "1 = 1"),
            "mv": ("ALL_MVIEWS", "MVIEW_NAME", "1 = 1"),
        }
        if table_type not in object_sql:
            raise DatusDbException(ErrorCode.COMMON_FIELD_INVALID, f"Invalid table type '{table_type}'")
        table_name, name_column, extra_filter = object_sql[table_type]
        sql = f"""
            SELECT OWNER, {name_column}
            FROM {table_name}
            WHERE {self._owner_filter(schema_name)}
              AND {extra_filter}
            ORDER BY OWNER, {name_column}
        """
        query_result = self._execute_pandas(sql)
        result = []
        for row in self._frame_rows(query_result, "OWNER", name_column):
            owner = row["OWNER"]
            object_name = row[name_column]
            result.append(
                {
                    "identifier": self.identifier(schema_name=owner, table_name=object_name),
                    "catalog_name": "",
                    "database_name": database_name or self.database_name,
                    "schema_name": owner,
                    "table_name": object_name,
                    "table_type": table_type,
                }
            )
        return result

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("table", catalog_name, database_name, schema_name)]

    @override
    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("view", catalog_name, database_name, schema_name)]

    @override
    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("mv", catalog_name, database_name, schema_name)]

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        return [self.database_name] if self.database_name else []

    @override
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        result = self._execute_pandas("SELECT USERNAME FROM ALL_USERS ORDER BY USERNAME")
        schemas = [row["USERNAME"] for row in self._frame_rows(result, "USERNAME")]
        if not include_sys:
            schemas = [schema for schema in schemas if schema not in self._sys_schemas()]
        return schemas
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datus-oracle/datus_oracle/connector.py datus-oracle/tests/unit/test_connector_unit.py
git commit -m "feat: add oracle metadata discovery"
```

---

### Task 5: Column Schema, DDL, Context, and Sample Rows

**Files:**
- Modify: `datus-oracle/datus_oracle/connector.py`
- Modify: `datus-oracle/tests/unit/test_connector_unit.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
def test_get_schema_returns_columns_with_pk_and_comments():
    connector = make_connector()
    connector._execute_pandas = MagicMock(
        return_value={
            "COLUMN_ID": [1],
            "COLUMN_NAME": ["ID"],
            "DATA_TYPE": ["NUMBER"],
            "DATA_PRECISION": [10],
            "DATA_SCALE": [0],
            "NULLABLE": ["N"],
            "DATA_DEFAULT": [None],
            "IS_PK": [1],
            "COMMENTS": ["primary id"],
        }
    )

    assert connector.get_schema(schema_name="APP", table_name="CUSTOMERS") == [
        {
            "cid": 0,
            "name": "ID",
            "type": "NUMBER(10,0)",
            "nullable": False,
            "default_value": None,
            "pk": True,
            "comment": "primary id",
        }
    ]


def test_do_switch_context_sets_current_schema():
    connector = make_connector()
    conn = MagicMock()

    connector.do_switch_context(conn, schema_name="REPORTING")

    sql = str(conn.execute.call_args.args[0])
    assert 'ALTER SESSION SET CURRENT_SCHEMA = "REPORTING"' in sql
    conn.commit.assert_called_once()


def test_get_ddl_calls_dbms_metadata():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value={"DDL": ['CREATE TABLE "APP"."CUSTOMERS" ("ID" NUMBER)']})

    assert connector._get_ddl("APP", "CUSTOMERS", "TABLE").startswith("CREATE TABLE")
    assert "DBMS_METADATA.GET_DDL" in connector._execute_pandas.call_args.args[0]


def test_sample_rows_uses_fetch_first():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value={"ID": [1]})

    rows = connector.get_sample_rows(tables=["CUSTOMERS"], top_n=3, schema_name="APP")

    assert rows[0]["table_name"] == "CUSTOMERS"
    assert "FETCH FIRST 3 ROWS ONLY" in connector._execute_pandas.call_args.args[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py -v
```

Expected: FAIL because these methods are not implemented.

- [ ] **Step 3: Implement schema, DDL, context, and samples**

Add methods to `OracleConnector`:

```python
    def _format_data_type(self, row: Dict[str, Any]) -> str:
        data_type = row["DATA_TYPE"]
        precision = row.get("DATA_PRECISION")
        scale = row.get("DATA_SCALE")
        if data_type == "NUMBER" and precision is not None:
            return f"NUMBER({precision},{scale or 0})"
        return data_type

    @override
    def get_schema(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> List[Dict[str, Any]]:
        if not table_name:
            return []
        owner = (schema_name or self.schema_name).upper().replace("'", "''")
        safe_table = table_name.upper().replace("'", "''")
        sql = f"""
            SELECT
                c.COLUMN_ID,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.DATA_PRECISION,
                c.DATA_SCALE,
                c.NULLABLE,
                c.DATA_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS IS_PK,
                cc.COMMENTS
            FROM ALL_TAB_COLUMNS c
            LEFT JOIN (
                SELECT cols.OWNER, cols.TABLE_NAME, cols.COLUMN_NAME
                FROM ALL_CONSTRAINTS cons
                JOIN ALL_CONS_COLUMNS cols
                  ON cons.OWNER = cols.OWNER
                 AND cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                 AND cons.TABLE_NAME = cols.TABLE_NAME
                WHERE cons.CONSTRAINT_TYPE = 'P'
                  AND cons.OWNER = '{owner}'
                  AND cons.TABLE_NAME = '{safe_table}'
            ) pk
              ON pk.OWNER = c.OWNER
             AND pk.TABLE_NAME = c.TABLE_NAME
             AND pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN ALL_COL_COMMENTS cc
              ON cc.OWNER = c.OWNER
             AND cc.TABLE_NAME = c.TABLE_NAME
             AND cc.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.OWNER = '{owner}'
              AND c.TABLE_NAME = '{safe_table}'
            ORDER BY c.COLUMN_ID
        """
        query_result = self._execute_pandas(sql)
        result = []
        for i, row in enumerate(
            self._frame_rows(
                query_result,
                "COLUMN_ID",
                "COLUMN_NAME",
                "DATA_TYPE",
                "DATA_PRECISION",
                "DATA_SCALE",
                "NULLABLE",
                "DATA_DEFAULT",
                "IS_PK",
                "COMMENTS",
            )
        ):
            result.append(
                {
                    "cid": i,
                    "name": row["COLUMN_NAME"],
                    "type": self._format_data_type(row),
                    "nullable": row["NULLABLE"] == "Y",
                    "default_value": row["DATA_DEFAULT"],
                    "pk": bool(row["IS_PK"]),
                    "comment": row["COMMENTS"] or None,
                }
            )
        return result

    def _get_ddl(self, schema_name: str, table_name: str, object_type: str = "TABLE") -> str:
        owner = schema_name.upper().replace("'", "''")
        object_name = table_name.upper().replace("'", "''")
        sql = f"""
            SELECT DBMS_METADATA.GET_DDL('{object_type}', '{object_name}', '{owner}') AS DDL
            FROM DUAL
        """
        result = self._execute_pandas(sql)
        rows = self._frame_rows(result, "DDL")
        if rows and rows[0]["DDL"]:
            return str(rows[0]["DDL"])
        return f"-- DDL not available for {self.full_name(schema_name=schema_name, table_name=table_name)}"

    def _get_objects_with_ddl(
        self,
        table_type: TABLE_TYPE = "table",
        tables: Optional[List[str]] = None,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[Dict[str, str]]:
        object_type_map = {"table": "TABLE", "view": "VIEW", "mv": "MATERIALIZED_VIEW"}
        result = []
        filter_tables = self._reset_filter_tables(tables, catalog_name, database_name, schema_name)
        for meta in self._get_metadata(table_type, catalog_name, database_name, schema_name):
            full_name = self.full_name(schema_name=meta["schema_name"], table_name=meta["table_name"])
            if filter_tables and full_name not in filter_tables:
                continue
            try:
                meta["definition"] = self._get_ddl(meta["schema_name"], meta["table_name"], object_type_map[table_type])
            except Exception as e:
                logger.warning(f"Could not get DDL for {full_name}: {e}")
                meta["definition"] = f"-- DDL not available for {meta['table_name']}"
            result.append(meta)
        return result

    @override
    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        return self._get_objects_with_ddl("table", tables, catalog_name, database_name, schema_name)

    @override
    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        return self._get_objects_with_ddl("view", None, catalog_name, database_name, schema_name)

    @override
    def do_switch_context(self, conn, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        if schema_name:
            conn.execute(text(f"ALTER SESSION SET CURRENT_SCHEMA = {self.quote_identifier(schema_name.upper())}"))
            conn.commit()

    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: TABLE_TYPE = "table",
    ) -> List[Dict[str, str]]:
        schema_name = schema_name or self.schema_name
        result = []
        target_tables = tables or self.get_tables(schema_name=schema_name)
        for table in target_tables:
            full_name = self.full_name(schema_name=schema_name, table_name=table)
            df = self._execute_pandas(f"SELECT * FROM {full_name} FETCH FIRST {top_n} ROWS ONLY")
            if hasattr(df, "empty") and df.empty:
                continue
            result.append(
                {
                    "identifier": self.identifier(schema_name=schema_name, table_name=table),
                    "catalog_name": "",
                    "database_name": self.database_name,
                    "schema_name": schema_name,
                    "table_name": table,
                    "sample_rows": df.to_csv(index=False) if hasattr(df, "to_csv") else str(df),
                }
            )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest datus-oracle/tests/unit/test_connector_unit.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datus-oracle/datus_oracle/connector.py datus-oracle/tests/unit/test_connector_unit.py
git commit -m "feat: add oracle schema and ddl support"
```

---

### Task 6: Integration Test Harness and Documentation

**Files:**
- Create: `datus-oracle/tests/integration/__init__.py`
- Create: `datus-oracle/tests/integration/conftest.py`
- Create: `datus-oracle/tests/integration/test_connection.py`
- Create: `datus-oracle/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write skipped-by-default integration tests**

Create `datus-oracle/tests/integration/conftest.py`:

```python
import os

import pytest

from datus_oracle import OracleConfig, OracleConnector


@pytest.fixture(scope="session")
def oracle_config():
    username = os.getenv("DATUS_ORACLE_USERNAME")
    password = os.getenv("DATUS_ORACLE_PASSWORD")
    service_name = os.getenv("DATUS_ORACLE_SERVICE_NAME", "FREEPDB1")
    if not username:
        pytest.skip("Set DATUS_ORACLE_USERNAME to run Oracle integration tests")
    return OracleConfig(
        host=os.getenv("DATUS_ORACLE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATUS_ORACLE_PORT", "1521")),
        username=username,
        password=password or "",
        service_name=service_name,
        schema=os.getenv("DATUS_ORACLE_SCHEMA", username),
    )


@pytest.fixture
def oracle_connector(oracle_config):
    connector = OracleConnector(oracle_config)
    try:
        yield connector
    finally:
        connector.close()
```

Create `datus-oracle/tests/integration/test_connection.py`:

```python
def test_oracle_connection_smoke(oracle_connector):
    result = oracle_connector.execute({"sql_query": "SELECT 1 AS value FROM DUAL"}, result_format="list")

    assert result.success is True


def test_oracle_metadata_smoke(oracle_connector, oracle_config):
    schemas = oracle_connector.get_schemas(include_sys=False)

    assert oracle_config.schema_name in schemas
```

- [ ] **Step 2: Run integration tests to verify they skip without env**

Run:

```bash
uv run pytest datus-oracle/tests/integration -v
```

Expected: SKIPPED when Oracle env vars are absent.

- [ ] **Step 3: Add README documentation**

Create `datus-oracle/README.md` with:

```markdown
# datus-oracle

Oracle database adapter for Datus.

## Installation

```bash
pip install datus-oracle
```

## Configuration

```yaml
database:
  type: oracle
  host: localhost
  port: 1521
  username: app
  password: secret
  database: FREEPDB1
  schema: APP
```

`database` is treated as Oracle `service_name`. Use `sid` instead for legacy SID-based connections.

## Python Usage

```python
from datus_oracle import OracleConfig, OracleConnector

connector = OracleConnector(
    OracleConfig(
        host="localhost",
        port=1521,
        username="app",
        password="secret",
        service_name="FREEPDB1",
        schema="APP",
    )
)

result = connector.execute({"sql_query": "SELECT 1 FROM DUAL"}, result_format="list")
tables = connector.get_tables(schema_name="APP")
columns = connector.get_schema(schema_name="APP", table_name="CUSTOMERS")
connector.close()
```

## Testing

```bash
uv run pytest datus-oracle/tests/unit -v
```

Integration tests require a reachable Oracle instance:

```bash
export DATUS_ORACLE_HOST=127.0.0.1
export DATUS_ORACLE_PORT=1521
export DATUS_ORACLE_USERNAME=app
export DATUS_ORACLE_PASSWORD=secret
export DATUS_ORACLE_SERVICE_NAME=FREEPDB1
export DATUS_ORACLE_SCHEMA=APP
uv run pytest datus-oracle/tests/integration -v
```
```

Modify root `README.md` to list `datus-oracle` under implemented adapters and mention that it uses SQLAlchemy plus `python-oracledb`.

- [ ] **Step 4: Run documentation-adjacent tests**

Run:

```bash
uv run pytest datus-oracle/tests/unit datus-oracle/tests/integration -v
```

Expected: unit tests PASS; integration tests SKIP without Oracle env.

- [ ] **Step 5: Commit**

```bash
git add README.md datus-oracle/README.md datus-oracle/tests/integration
git commit -m "docs: document oracle adapter"
```

---

### Task 7: Formatting, Full Unit Verification, and Final Commit

**Files:**
- Modify as needed based on formatter/linter output.

- [ ] **Step 1: Run Oracle unit tests**

Run:

```bash
uv run pytest datus-oracle/tests/unit -v
```

Expected: PASS.

- [ ] **Step 2: Run package import smoke**

Run:

```bash
uv run python -c "from datus_oracle import OracleConfig, OracleConnector; print(OracleConfig(username='app').database, OracleConnector)"
```

Expected: prints `FREEPDB1` and an `OracleConnector` class reference.

- [ ] **Step 3: Run format checks on Oracle package**

Run:

```bash
uv run ruff check datus-oracle
uv run black --check --line-length=120 datus-oracle
uv run isort --check-only --profile=black --line-length=120 datus-oracle
```

Expected: PASS. If formatting fails, run:

```bash
uv run black --line-length=120 datus-oracle
uv run isort --profile=black --line-length=120 datus-oracle
uv run ruff check datus-oracle --fix
```

Then rerun the checks.

- [ ] **Step 4: Run existing SQLAlchemy-adjacent unit tests**

Run:

```bash
uv run pytest datus-sqlalchemy/tests/unit datus-postgresql/tests/unit datus-mysql/tests/unit datus-oracle/tests/unit -v
```

Expected: PASS. If unrelated pre-existing failures appear, capture the failing test names and do not modify unrelated adapters unless the Oracle change caused the failure.

- [ ] **Step 5: Commit any verification fixes**

If formatting or small test fixes changed files:

```bash
git add datus-oracle README.md pyproject.toml
git commit -m "chore: polish oracle adapter"
```

If no files changed, do not create an empty commit.

---

## Self-Review Checklist

- [ ] `datus-oracle` follows the same package shape as `datus-postgresql` and `datus-mysql`.
- [ ] Oracle is registered through `[project.entry-points."datus.adapters"]`.
- [ ] Root workspace includes `datus-oracle`.
- [ ] Config supports both `database` alias and explicit `service_name`.
- [ ] `service_name` and `sid` are mutually exclusive.
- [ ] Metadata methods use Oracle catalog views and exclude system schemas by default.
- [ ] SQL qualification uses `"SCHEMA"."TABLE"` rather than service/database qualification.
- [ ] Integration tests skip unless env vars are present.
- [ ] Each task ends with a commit.
- [ ] Final verification results are recorded in the final response.

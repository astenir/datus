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

## Features

- SQL execution through SQLAlchemy and `python-oracledb`
- Service name and SID connection modes
- Schema/user metadata discovery
- Tables, views, and materialized views
- Column metadata, comments, and primary-key detection
- DDL retrieval through `DBMS_METADATA.GET_DDL`
- Sample rows with Oracle `FETCH FIRST` syntax

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

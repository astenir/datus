# datus-hive

Hive database adapter for Datus.

## Installation

```bash
pip install datus-hive
```

This will automatically install the required dependencies:
- `datus-agent`
- `datus-sqlalchemy`
- `pyhive`
- `thrift`
- `thrift-sasl`
- `pure-sasl`

## Usage

The adapter is automatically registered with Datus when installed. Configure your Hive connection in your Datus configuration:

```yaml
namespace:
  hive:
    type: hive
    host: 127.0.0.1
    port: 10000
    username: hive
    database: default
```

With authentication and session configuration:

```yaml
namespace:
  hive_production:
    type: hive
    host: 127.0.0.1
    port: 10000
    database: mydb
    username: hive_user
    password: your_password
    auth: CUSTOM
    configuration:
      hive.execution.engine: spark
      spark.app.name: my_app
      spark.executor.memory: 1G
      spark.executor.instances: 2
```

Or use programmatically:

```python
from datus_hive import HiveConnector, HiveConfig

# Create connector
config = HiveConfig(
    host="127.0.0.1",
    port=10000,
    database="default",
    username="hive",
)

connector = HiveConnector(config)

# Test connection
connector.test_connection()

# Execute query
result = connector.execute(
    {"sql_query": "SELECT * FROM my_table LIMIT 10"},
    result_format="list",
)
print(result.sql_return)

# Get table list
tables = connector.get_tables()
print(f"Tables: {tables}")

# Get table schema
schema = connector.get_schema(table_name="my_table")
for column in schema:
    print(f"{column['name']}: {column['type']}")
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | `127.0.0.1` | HiveServer2 host |
| `port` | int | `10000` | HiveServer2 Thrift port |
| `database` | str | `None` | Default database (falls back to `default`) |
| `username` | str | **required** | Hive username |
| `password` | str | `""` | Password (for LDAP/CUSTOM auth) |
| `auth` | str | `None` | Auth mechanism: `NONE`, `LDAP`, `CUSTOM`, `KERBEROS` |
| `configuration` | dict | `{}` | Hive session configuration key-value pairs |
| `timeout_seconds` | int | `30` | Connection timeout in seconds |

## Features

- Query execution with multiple result formats (list, csv, pandas, arrow)
- DDL execution (CREATE, ALTER, DROP)
- Metadata retrieval (databases, tables, views, schemas)
- DDL retrieval (SHOW CREATE TABLE)
- Sample data extraction
- Database context switching (USE statement)
- Connection pooling and management
- Hive session configuration support

## Testing

### Unit Tests

```bash
uv run pytest datus-hive/tests/unit -v
```

### Integration Tests

Start Hive using Docker:

```bash
cd datus-hive
docker compose up -d

# Wait for Hive to be healthy (about 1-2 minutes)
docker inspect --format='{{.State.Health.Status}}' datus-hive-server
```

Run integration tests:

```bash
uv run pytest datus-hive/tests/integration -v
```

Stop Hive:

```bash
cd datus-hive
docker compose down
```

### TPC-H Test Data

Initialize TPC-H sample data for manual testing:

```bash
uv run python datus-hive/scripts/init_tpch_data.py

# With custom connection:
uv run python datus-hive/scripts/init_tpch_data.py --host localhost --port 10000 --username hive

# Clean re-init (drop existing tables first):
uv run python datus-hive/scripts/init_tpch_data.py --drop
```

This creates 5 TPC-H tables with sample data:

| Table | Rows |
|-------|------|
| `tpch_region` | 5 |
| `tpch_nation` | 25 |
| `tpch_customer` | 10 |
| `tpch_orders` | 15 |
| `tpch_supplier` | 5 |

## Requirements

- Python >= 3.10
- Apache Hive >= 2.x (tested with 4.0.1)
- datus-agent >= 0.3.0
- datus-sqlalchemy >= 0.1.0
- pyhive >= 0.7.0

## License

Apache License 2.0

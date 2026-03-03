# datus-clickhouse

ClickHouse database adapter for Datus.

## Installation

```bash
pip install datus-clickhouse
```

This will automatically install the required dependencies:
- `datus-agent`
- `datus-sqlalchemy`
- `clickhouse-sqlalchemy`

## Usage

The adapter is automatically registered with Datus when installed. Configure your database connection in your Datus configuration:

```yaml
database:
  type: clickhouse
  host: localhost
  port: 8123
  username: default
  password: your_password
  database: your_database
```

Or use programmatically:

```python
from datus_clickhouse import ClickHouseConfig, ClickHouseConnector

# Using config object
config = ClickHouseConfig(
    host="localhost",
    port=8123,
    username="default",
    password="your_password",
    database="mydb",
)
connector = ClickHouseConnector(config)

# Or using dict
connector = ClickHouseConnector({
    "host": "localhost",
    "port": 8123,
    "username": "default",
    "password": "your_password",
    "database": "mydb",
})

# Test connection
connector.test_connection()

# Execute query
result = connector.execute({"sql_query": "SELECT * FROM users LIMIT 10"})
print(result.sql_return)

# Get table list
tables = connector.get_tables()
print(f"Tables: {tables}")

# Get table schema
schema = connector.get_schema(table_name="users")
for column in schema:
    print(f"{column['name']}: {column['type']}")
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| host | str | "localhost" | ClickHouse server host |
| port | int | 8123 | ClickHouse HTTP port |
| username | str | (required) | Username |
| password | str | "" | Password |
| database | str | None | Default database |
| timeout_seconds | int | 30 | Connection timeout |

## Features

- Query execution via ClickHouse SQL (SELECT)
- DDL execution (CREATE, ALTER, DROP)
- DML operations (INSERT, ALTER TABLE UPDATE, DELETE)
- Metadata retrieval (databases, tables, views, columns)
- Sample data extraction
- Multiple result formats (pandas, arrow, csv, list)
- Connection pooling and management
- Comprehensive error handling

## Testing

### Quick Start

```bash
cd datus-clickhouse

# Unit tests (no database required)
uv run pytest tests/ -m "not integration" -v

# All tests with coverage
uv run pytest tests/ -v --cov=datus_clickhouse --cov-report=term-missing
```

### Integration Tests (Requires ClickHouse Server)

```bash
# Start ClickHouse container
docker compose up -d

# Wait for container to become healthy (~15s)
docker compose ps

# Run integration tests
uv run pytest tests/integration/ -v

# Run only TPC-H tests
uv run pytest tests/integration/test_tpch.py -v

# Run acceptance tests (core functionality)
uv run pytest tests/ -m acceptance -v

# Stop ClickHouse
docker compose down
```

### TPC-H Test Data

Integration tests include TPC-H benchmark data for realistic query testing. The `tpch_setup` fixture (session-scoped) automatically creates 5 tables with sample data:

| Table | Rows | Description |
|-------|------|-------------|
| `tpch_region` | 5 | Standard TPC-H regions |
| `tpch_nation` | 25 | Standard TPC-H nations |
| `tpch_customer` | 10 | Simplified customer data |
| `tpch_orders` | 15 | Simplified order data |
| `tpch_supplier` | 5 | Simplified supplier data |

Tables are created at the start of the test session and dropped after all tests complete.

#### Initialize TPC-H Data Manually

To create TPC-H data for use with Datus (outside of tests):

```bash
# Basic usage
uv run python scripts/init_tpch_data.py

# Drop existing tables and re-create
uv run python scripts/init_tpch_data.py --drop

# Custom connection
uv run python scripts/init_tpch_data.py --host 192.168.1.100 --port 8123 --username admin --password secret
```

### Test Statistics

- **Unit Tests**: 45 tests (config validation, connector logic, identifiers)
- **Integration Tests**: 20 tests (connection, metadata, SQL execution)
- **TPC-H Tests**: 9 tests (metadata queries, joins, aggregations, CSV format)
- **Total**: 74 tests

### Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires running ClickHouse server |
| `acceptance` | Core functionality validation for CI/CD |

## Development

### Setup

```bash
# From workspace root
uv sync --all-packages

# Or install in editable mode
uv pip install -e .
```

### Code Quality

```bash
black datus_clickhouse tests
isort datus_clickhouse tests
ruff check datus_clickhouse tests
```

## ClickHouse SQL Notes

ClickHouse has some syntax differences from standard SQL:

- **UPDATE**: Use `ALTER TABLE <table> UPDATE ... WHERE ...` instead of `UPDATE <table> SET ...`
- **DELETE**: Supports lightweight deletes with `DELETE FROM <table> WHERE ...`
- **Identifiers**: Use backticks for quoting: `` `database`.`table` ``
- **No schema layer**: Databases serve as schemas; there is no separate schema concept

## Requirements

- Python >= 3.12
- ClickHouse >= 20.1
- datus-agent > 0.2.1
- datus-sqlalchemy >= 0.1.0
- clickhouse-sqlalchemy >= 0.3.2

## License

Apache License 2.0

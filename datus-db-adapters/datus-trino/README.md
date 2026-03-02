# datus-trino

Trino database adapter for Datus.

## Installation

```bash
pip install datus-trino
```

This will automatically install the required dependencies:
- `datus-agent`
- `datus-sqlalchemy`
- `trino`

## Usage

The adapter is automatically registered with Datus when installed. Configure your database connection in your Datus configuration:

```yaml
database:
  type: trino
  host: localhost
  port: 8080
  username: trino
  catalog: memory
  schema_name: default
```

Or use programmatically:

```python
from datus_trino import TrinoConnector, TrinoConfig

# Using config object
config = TrinoConfig(
    host="localhost",
    port=8080,
    username="trino",
    catalog="memory",
    schema_name="default",
)
connector = TrinoConnector(config)

# Or using dict
connector = TrinoConnector({
    "host": "localhost",
    "port": 8080,
    "username": "trino",
    "catalog": "memory",
    "schema_name": "default",
})

# Test connection
connector.test_connection()

# Execute query
result = connector.execute({"sql_query": 'SELECT * FROM "tpch"."tiny"."nation"'})
print(result.sql_return)

# Get catalogs
catalogs = connector.get_catalogs()
print(f"Catalogs: {catalogs}")

# Get table list
tables = connector.get_tables(catalog_name="tpch", schema_name="tiny")
print(f"Tables: {tables}")

# Get table schema
schema = connector.get_schema(catalog_name="tpch", schema_name="tiny", table_name="nation")
for column in schema:
    print(f"{column['name']}: {column['type']}")
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| host | str | "127.0.0.1" | Trino server host |
| port | int | 8080 | Trino server port |
| username | str | (required) | Username |
| password | str | "" | Password |
| catalog | str | "hive" | Default catalog |
| schema_name | str | "default" | Default schema |
| http_scheme | str | "http" | HTTP scheme (http/https) |
| verify | bool | True | Verify SSL certificates |
| timeout_seconds | int | 30 | Connection timeout |

## Features

- Query execution via Trino SQL
- DDL execution (CREATE, ALTER, DROP)
- Three-level hierarchy: catalog -> schema -> table
- Catalog switching (cross-catalog queries)
- Metadata retrieval (catalogs, schemas, tables, views, columns)
- Sample data extraction
- Multiple result formats (pandas, arrow, csv, list)
- Connection pooling and management

## Testing

### Quick Start

```bash
cd datus-trino

# Unit tests (no database required)
uv run pytest tests/ -m "not integration" -v

# All tests with coverage
uv run pytest tests/ -v --cov=datus_trino --cov-report=term-missing
```

### Integration Tests (Requires Trino)

```bash
# Start Trino container (with TPC-H connector pre-configured)
docker compose up -d

# Wait for container to become healthy (~30s)
docker compose ps

# Run integration tests
uv run pytest tests/integration/ -v

# Run only TPC-H tests
uv run pytest tests/integration/test_tpch.py -v

# Run acceptance tests (core functionality)
uv run pytest tests/ -m acceptance -v

# Stop Trino
docker compose down
```

### TPC-H Test Data

Trino has a built-in TPC-H connector that generates benchmark data on-the-fly using deterministic algorithms. No data import is needed. The Docker setup includes `etc/catalog/tpch.properties` which enables this connector.

Available schemas (scale factors):

| Schema | Description |
|--------|-------------|
| `tiny` | ~10 rows per table (default for tests) |
| `sf1` | Scale factor 1 (~1.5M orders) |
| `sf100` | Scale factor 100 (~150M orders) |
| `sf1000` | Scale factor 1000 (~1.5B orders) |

Standard TPC-H tables (8 total):

`customer`, `lineitem`, `nation`, `orders`, `part`, `partsupp`, `region`, `supplier`

#### Datus Agent Configuration

To use TPC-H data in Datus agent:

```yaml
# In agent.yml under namespace
trino_tpch:
  type: trino
  host: 127.0.0.1
  port: 8080
  username: trino
  catalog: tpch
  schema_name: tiny
```

### Test Statistics

- **Unit Tests**: 49 tests (config validation, connector logic, identifiers)
- **Integration Tests**: 23 tests (connection, metadata, SQL execution, TPC-H)
- **Total**: 72 tests

### Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires running Trino server |
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
black datus_trino tests
isort datus_trino tests
ruff check datus_trino tests
```

## Requirements

- Python >= 3.12
- Trino >= 400
- datus-agent > 0.2.1
- datus-sqlalchemy >= 0.1.0

## License

Apache License 2.0

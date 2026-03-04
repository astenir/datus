# datus-redshift

Amazon Redshift database adapter for Datus.

## Installation

```bash
pip install datus-redshift
```

This will automatically install the required dependencies:
- `datus-agent`
- `redshift_connector`

## Usage

The adapter is automatically registered with Datus when installed. Configure your database connection in your Datus configuration:

```yaml
database:
  type: redshift
  host: your-cluster.xxx.us-west-2.redshift.amazonaws.com
  port: 5439
  username: your_username
  password: your_password
  database: dev
  schema: public
```

Or use programmatically:

```python
from datus_redshift import RedshiftConfig, RedshiftConnector

# Using config object
config = RedshiftConfig(
    host="your-cluster.xxx.us-west-2.redshift.amazonaws.com",
    username="your_username",
    password="your_password",
    database="dev",
    schema="public",
    port=5439,
    ssl=True,
)
connector = RedshiftConnector(config)

# Test connection
connector.test_connection()

# Execute query
result = connector.execute_query("SELECT * FROM users LIMIT 10", result_format="list")
print(result.sql_return)

# Get table list
tables = connector.get_tables(schema_name="public")
print(f"Tables: {tables}")

# Get table schema
schema = connector.get_schema(table_name="users")
for column in schema:
    print(f"{column['name']}: {column['type']}")

# Close connection when done
connector.close()
```

### IAM Authentication

> **Recommended**: Use IAM role-based authentication instead of embedding static
> credentials. When running on EC2/ECS/Lambda with an attached IAM role, omit
> `access_key_id` and `secret_access_key` -- the SDK will use the instance
> profile credentials automatically.

```python
config = RedshiftConfig(
    host="your-cluster.xxx.us-west-2.redshift.amazonaws.com",
    username="your_iam_user",
    database="dev",
    iam=True,
    cluster_identifier="your-cluster-identifier",
    region="us-west-2",
    # Omit access_key_id/secret_access_key when using IAM role-based auth.
    # Only set these for local development with static credentials:
    # access_key_id="YOUR_ACCESS_KEY",
    # secret_access_key="YOUR_SECRET_KEY",
)
connector = RedshiftConnector(config)
```

### Query Result Formats

```python
# CSV string
result = connector.execute_query("SELECT * FROM my_table", result_format="csv")

# Pandas DataFrame
result = connector.execute_query("SELECT * FROM my_table", result_format="pandas")

# Arrow table (best for large datasets)
result = connector.execute_query("SELECT * FROM my_table", result_format="arrow")

# List of dictionaries
result = connector.execute_query("SELECT * FROM my_table", result_format="list")
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| host | str | (required) | Redshift cluster endpoint |
| username | str | (required) | Username for authentication |
| password | str | (required) | Password for authentication |
| port | int | 5439 | Redshift port |
| database | str | None | Default database |
| schema | str | None | Default schema (uses 'public' if not specified) |
| timeout_seconds | int | 30 | Connection timeout |
| ssl | bool | True | Enable SSL/TLS connection |
| iam | bool | False | Use IAM authentication |
| cluster_identifier | str | None | Cluster ID for IAM auth |
| region | str | None | AWS region for IAM auth |
| access_key_id | str | None | AWS access key for IAM auth |
| secret_access_key | str | None | AWS secret key for IAM auth |

## Features

- Query execution via Redshift SQL (SELECT)
- DDL execution (CREATE, ALTER, DROP)
- DML operations (INSERT, UPDATE, DELETE)
- Metadata retrieval (databases, schemas, tables, views, materialized views, columns)
- Sample data extraction
- Multiple result formats (pandas, arrow, csv, list)
- Connection management with SSL/TLS support
- IAM authentication support
- Comprehensive error handling with exception mapping

## Testing

### Quick Start

```bash
cd datus-redshift

# Unit tests (no database required)
uv run pytest tests/unit/ -v

# All unit tests with coverage
uv run pytest tests/unit/ -v --cov=datus_redshift --cov-report=term-missing
```

### Integration Tests (Requires Redshift Cluster)

Integration tests require a running Redshift cluster. Set these environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDSHIFT_HOST` | Yes | - | Redshift cluster endpoint |
| `REDSHIFT_USERNAME` | Yes | - | Username |
| `REDSHIFT_PASSWORD` | Yes | - | Password |
| `REDSHIFT_DATABASE` | No | `dev` | Database name |
| `REDSHIFT_PORT` | No | `5439` | Port |
| `REDSHIFT_SCHEMA` | No | `public` | Schema |

```bash
# Set credentials
export REDSHIFT_HOST="my-cluster.abc123.us-west-2.redshift.amazonaws.com"
export REDSHIFT_USERNAME="admin"
export REDSHIFT_PASSWORD="secret"

# Run all integration tests
uv run pytest tests/integration/ -v

# Run only connector tests
uv run pytest tests/integration/test_connector.py -v

# Run only TPC-H tests
uv run pytest tests/integration/test_tpch.py -v

# Run acceptance tests (core functionality)
uv run pytest tests/ -m acceptance -v
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
# Basic usage (with environment variables)
uv run python scripts/init_tpch_data.py

# Drop existing tables and re-create
uv run python scripts/init_tpch_data.py --drop

# Custom connection
uv run python scripts/init_tpch_data.py \
  --host my-cluster.abc123.us-west-2.redshift.amazonaws.com \
  --username admin \
  --password secret

# Use a custom schema
uv run python scripts/init_tpch_data.py --schema my_test_schema
```

### Test Statistics

- **Unit Tests**: 53 tests (config validation, connector logic, exception handling, identifiers)
- **Integration Tests**: 11 tests (connection, metadata, SQL execution, output formats)
- **TPC-H Tests**: 11 tests (metadata queries, joins, aggregations, multiple formats)
- **Total**: 75 tests

### Test Markers

| Marker | Description |
|--------|-------------|
| `integration` | Requires running Redshift cluster |
| `acceptance` | Core functionality validation for CI/CD |

## Development

### Setup

```bash
# From workspace root
uv sync --all-packages

# Or install in editable mode
uv pip install -e .
```

### Code Structure

```
datus-redshift/
├── datus_redshift/
│   ├── __init__.py       # Module initialization and registration
│   ├── config.py         # Configuration class (RedshiftConfig)
│   └── connector.py      # Main connector implementation (RedshiftConnector)
├── tests/
│   ├── conftest.py       # Shared test configuration and markers
│   ├── unit/
│   │   ├── test_config.py          # Config validation tests
│   │   └── test_connector_unit.py  # Connector unit tests
│   └── integration/
│       ├── conftest.py             # Integration fixtures and TPC-H data
│       ├── test_connector.py       # Connector integration tests
│       └── test_tpch.py            # TPC-H query tests
├── scripts/
│   └── init_tpch_data.py  # TPC-H data initialization script
├── pyproject.toml         # Package configuration
└── README.md              # This file
```

### Code Quality

```bash
black datus_redshift tests
isort datus_redshift tests
ruff check datus_redshift tests
```

## Redshift SQL Notes

Redshift is based on PostgreSQL but has some differences:

- **Identifiers**: Use double quotes for quoting: `"schema"."table"`
- **No IF NOT EXISTS for schemas**: Use `CREATE SCHEMA` without `IF NOT EXISTS` in older versions
- **DECIMAL precision**: Use `DECIMAL(15,2)` for monetary values
- **VARCHAR limits**: Default VARCHAR is 256 chars; specify length explicitly
- **Distribution styles**: Use `DISTSTYLE`, `DISTKEY`, `SORTKEY` for performance tuning

## Troubleshooting

### Connection Issues

1. **Timeout errors**: Increase `timeout_seconds` in the configuration
2. **SSL errors**: Try setting `ssl=False` if your cluster doesn't require SSL
3. **IAM auth fails**: Verify your AWS credentials and cluster identifier are correct
4. **VPC access**: Ensure your network can reach the Redshift endpoint (security groups, VPN)

### Query Performance

1. Use `result_format="arrow"` for large result sets (most efficient)
2. Always specify schema names to avoid scanning all schemas
3. Use LIMIT clauses for exploratory queries

## Requirements

- Python >= 3.8
- datus-agent >= 0.2.1
- redshift_connector >= 2.0.0
- pyarrow (installed with datus-agent)
- pandas (installed with datus-agent)

## License

Apache License 2.0

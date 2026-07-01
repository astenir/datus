# Datus Snowflake Adapter

Snowflake database adapter for Datus Agent, providing native Snowflake connector support.

## Features

- **Native Snowflake SDK**: Uses `snowflake-connector-python` for optimal performance
- **Full Snowflake Support**: Databases, schemas, tables, views, and materialized views
- **Efficient Metadata Retrieval**: Uses SHOW commands for fast metadata queries
- **Arrow-based Execution**: High-performance query execution with Apache Arrow
- **Multiple Result Formats**: CSV, Pandas DataFrame, Arrow Table, and Python list
- **Complete CRUD Operations**: INSERT, UPDATE, DELETE, and DDL support

## Installation

```bash
pip install datus-snowflake
```

This will automatically install the required dependencies:
- `datus-agent>=0.3.0`
- `snowflake-connector-python>=3.6.0`

## Usage

### Basic Connection

```python
from datus_snowflake import SnowflakeConnector

# Create connector
connector = SnowflakeConnector(
    {
        "account": "myaccount",
        "username": "myuser",
        "password": "mypassword",
        "warehouse": "my_warehouse",
        "database": "my_database",
        "schema": "my_schema",
    }
)

# Test connection
result = connector.test_connection()
print(result)  # {'success': True, 'message': 'Connection successful', 'databases': ''}
```

### Key Pair Authentication (recommended for MFA accounts and CI)

Snowflake accounts with MFA enabled reject plain password logins from non-interactive
clients. Use RSA key pair authentication (`SNOWFLAKE_JWT`) instead — it bypasses MFA
and is Snowflake's recommended path for programmatic access. Register the public key
on your Snowflake user once (`ALTER USER <u> SET RSA_PUBLIC_KEY = '<base64>'`).

For hosted/SaaS deployments, store the private key as an encrypted secret field and
pass it as `private_key`; this avoids writing private keys to local files:

```python
from datus_snowflake import SnowflakeConnector

connector = SnowflakeConnector(
    {
        "account": "myaccount",
        "username": "myuser",
        "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
        # Only needed if the private key is encrypted:
        "private_key_file_pwd": "key-passphrase",
        "warehouse": "my_warehouse",
        "database": "my_database",
        "schema": "my_schema",
    }
)
```

For local or CI setups where a key file is already available, point the connector at
the matching private key file:

```python
from datus_snowflake import SnowflakeConnector

connector = SnowflakeConnector(
    {
        "account": "myaccount",
        "username": "myuser",
        "private_key_file": "/path/to/rsa_key.p8",
        # Only needed if the key file is encrypted:
        "private_key_file_pwd": "key-passphrase",
        "warehouse": "my_warehouse",
        "database": "my_database",
        "schema": "my_schema",
    }
)
```

`private_key` takes precedence over `private_key_file` and `password` when
provided. Without `private_key`, exactly one of `password` or `private_key_file`
must be provided; passing both (or neither) raises a `ValueError`.

### Execute Queries

```python
# Execute query and get CSV result
result = connector.execute_query("SELECT * FROM users LIMIT 10")
print(result.sql_return)  # CSV string

# Execute query and get pandas DataFrame
result = connector.execute_query("SELECT * FROM users LIMIT 10", result_format="pandas")
df = result.sql_return
print(df.head())

# Execute query and get Arrow table
result = connector.execute_query("SELECT * FROM users LIMIT 10", result_format="arrow")
arrow_table = result.sql_return
print(arrow_table.schema)
```

### Metadata Operations

```python
# Get databases
databases = connector.get_databases()
print(f"Databases: {databases}")

# Get schemas
schemas = connector.get_schemas(database_name="my_database")
print(f"Schemas: {schemas}")

# Get tables
tables = connector.get_tables(database_name="my_database", schema_name="public")
print(f"Tables: {tables}")

# Get views
views = connector.get_views(database_name="my_database", schema_name="public")
print(f"Views: {views}")

# Get materialized views
mvs = connector.get_materialized_views(database_name="my_database", schema_name="public")
print(f"Materialized Views: {mvs}")
```

### Get Table Schema

```python
# Get table structure
schema = connector.get_schema(
    database_name="my_database",
    schema_name="public",
    table_name="users"
)

for column in schema[:-1]:  # Last item is table metadata
    print(f"{column['name']}: {column['type']} (nullable: {column['nullable']})")
```

### Get DDL Definitions

```python
# Get tables with DDL
tables_with_ddl = connector.get_tables_with_ddl(
    database_name="my_database",
    schema_name="public"
)

for table in tables_with_ddl:
    print(f"\nTable: {table['table_name']}")
    print(f"DDL:\n{table['definition']}")

# Get views with DDL
views_with_ddl = connector.get_views_with_ddl(
    database_name="my_database",
    schema_name="public"
)

# Get materialized views with DDL
mvs_with_ddl = connector.get_materialized_views_with_ddl(
    database_name="my_database",
    schema_name="public"
)
```

### Get Sample Data

```python
# Get sample rows from specific tables
samples = connector.get_sample_rows(
    tables=["users", "orders"],
    top_n=5,
    database_name="my_database",
    schema_name="public"
)

for sample in samples:
    print(f"\nTable: {sample['table_name']}")
    print(sample['sample_rows'])  # CSV format
```

### CRUD Operations

```python
# INSERT
result = connector.execute_insert(
    "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
)
print(f"Inserted rows: {result.row_count}")

# UPDATE
result = connector.execute_update(
    "UPDATE users SET email = 'newemail@example.com' WHERE name = 'John'"
)
print(f"Updated rows: {result.row_count}")

# DELETE
result = connector.execute_delete(
    "DELETE FROM users WHERE name = 'John'"
)
print(f"Deleted rows: {result.row_count}")

# DDL
result = connector.execute_ddl(
    "CREATE TABLE test_table (id INT, name VARCHAR(100))"
)
print(f"DDL executed: {result.success}")
```

### Context Switching

```python
# Switch database
connector.do_switch_context(database_name="another_database")

# Switch schema
connector.do_switch_context(
    database_name="my_database",
    schema_name="another_schema"
)
```

## Configuration with Datus Agent

When using with Datus Agent, the adapter is automatically discovered via entry points:

```yaml
# config.yaml — password authentication
database:
  type: snowflake
  account: myaccount
  username: myuser
  password: mypassword
  warehouse: my_warehouse
  database: my_database
  schema: my_schema
```

```yaml
# config.yaml — key pair authentication with an in-memory/DB-backed PEM secret
database:
  type: snowflake
  account: myaccount
  username: myuser
  private_key: |
    -----BEGIN PRIVATE KEY-----
    ...
    -----END PRIVATE KEY-----
  # private_key_file_pwd: key-passphrase   # only for encrypted keys
  warehouse: my_warehouse
  database: my_database
  schema: my_schema
```

```yaml
# config.yaml — key pair authentication with a local file
database:
  type: snowflake
  account: myaccount
  username: myuser
  private_key_file: /path/to/rsa_key.p8
  # private_key_file_pwd: key-passphrase   # only for encrypted keys
  warehouse: my_warehouse
  database: my_database
  schema: my_schema
```

The adapter will be automatically loaded when you use `type: snowflake`.

## Architecture

This adapter:
- Inherits from `BaseSqlConnector` in `datus-agent`
- Uses native Snowflake connector for optimal performance
- Implements all required abstract methods
- Provides Snowflake-specific optimizations (SHOW commands, Arrow format)

## Development

```bash
# Install in development mode
cd datus-snowflake
pip install -e .

# Run tests
pytest tests/
```

## License

Apache License 2.0

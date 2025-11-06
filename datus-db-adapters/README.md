# Datus Database Adapters

Independent database adapter packages for Datus Agent.

## Overview

This repository contains database adapter implementations for Datus Agent, using a plugin architecture where each database is an independent package that can be installed on demand.

## Architecture

```
datus-agent (Core package - SQLite/DuckDB only)
    ↓
Plugin Adapters (Independent packages, install as needed)
├── datus-sqlalchemy (SQLAlchemy base layer)
│   ├── datus-mysql
│   ├── datus-starrocks
│   └── datus-postgresql (coming soon)
│
└── Native SDK Adapters
    ├── datus-snowflake
    ├── datus-clickhouse (coming soon)
    └── datus-bigquery (coming soon)
```

## Implemented Adapters

### 1. datus-sqlalchemy
SQLAlchemy base connector providing shared functionality for SQLAlchemy-based adapters.

**Installation**:
```bash
pip install datus-sqlalchemy
```

**Features**:
- SQLAlchemy engine and connection management
- Unified error handling
- Multiple result format support
- Connection pool management
- Metadata retrieval

---

### 2. datus-mysql
MySQL database adapter.

**Installation**:
```bash
pip install datus-mysql
```

**Features**:
- Full MySQL support
- INFORMATION_SCHEMA metadata queries
- SHOW CREATE statement support
- Complete CRUD operations

**Usage Example**:
```python
from datus_mysql import MySQLConnector

connector = MySQLConnector(
    host="localhost",
    port=3306,
    user="root",
    password="password",
    database="mydb"
)

# Execute query
result = connector.execute_query("SELECT * FROM users LIMIT 10")
print(result.sql_return)
```

---

### 3. datus-starrocks
StarRocks database adapter (MySQL protocol compatible).

**Installation**:
```bash
pip install datus-starrocks
```

**Features**:
- Inherits all MySQL functionality
- Multi-Catalog support
- Materialized view support
- StarRocks-specific optimizations

**Usage Example**:
```python
from datus_starrocks import StarRocksConnector

connector = StarRocksConnector(
    host="localhost",
    port=9030,
    user="root",
    password="password",
    catalog="default_catalog",
    database="mydb"
)

# Get catalogs
catalogs = connector.get_catalogs()
print(f"Catalogs: {catalogs}")

# Get materialized views
mvs = connector.get_materialized_views(database_name="mydb")
print(f"Materialized Views: {mvs}")
```

---

### 4. datus-snowflake
Snowflake database adapter (native SDK).

**Installation**:
```bash
pip install datus-snowflake
```

**Features**:
- Native Snowflake SDK
- Multi-database and schema support
- Tables, views, and materialized views
- Efficient SHOW commands
- Arrow format support

**Usage Example**:
```python
from datus_snowflake import SnowflakeConnector

connector = SnowflakeConnector(
    account="myaccount",
    user="myuser",
    password="mypassword",
    warehouse="my_warehouse",
    database="my_database",
    schema="my_schema"
)

# Execute query (multiple formats)
result = connector.execute_query("SELECT * FROM users LIMIT 10", result_format="pandas")
df = result.sql_return
print(df.head())

# Get databases
databases = connector.get_databases()
print(f"Databases: {databases}")
```

---

## Coming Soon

### datus-postgresql
PostgreSQL database adapter (SQLAlchemy-based).

### datus-clickhouse
ClickHouse database adapter (native SDK).

### datus-bigquery
Google BigQuery adapter (cloud service SDK).

### datus-oracle
Oracle database adapter (SQLAlchemy-based).

---

## Development Guide

### Development Environment Setup

This repository uses workspace configuration to manage multiple adapter packages:

```bash
# Clone repository
git clone https://github.com/your-org/Datus-adapters.git
cd Datus-adapters

# Install all adapters (development mode)
uv sync

# Or use pip
pip install -e datus-sqlalchemy
pip install -e datus-mysql
pip install -e datus-starrocks
pip install -e datus-snowflake
```

**Note**: The root `pyproject.toml` is only for development environment management. End users should install individual packages.

### Creating a New Adapter

1. **Choose Base Layer**:
   - If database is SQL standard compatible, inherit from `datus-sqlalchemy`
   - If native SDK is needed, inherit directly from `BaseSqlConnector`

2. **Create Package Structure**:
```bash
datus-<database>/
├── datus_<database>/
│   ├── __init__.py
│   └── connector.py
├── tests/
├── pyproject.toml
└── README.md
```

3. **Implement Connector**:
```python
from datus.tools.db_tools.base import BaseSqlConnector

class MyDatabaseConnector(BaseSqlConnector):
    def __init__(self, ...):
        super().__init__(dialect="mydatabase")
        # Initialize connection
    
    # Implement required abstract methods
    def execute_query(self, sql: str) -> ExecuteSQLResult:
        ...
```

4. **Configure Entry Point**:
```toml
[project.entry-points."datus.adapters"]
mydatabase = "datus_mydatabase:register"
```

5. **Registration Function**:
```python
# __init__.py
from datus.tools.db_tools import connector_registry
from .connector import MyDatabaseConnector

def register():
    connector_registry.register("mydatabase", MyDatabaseConnector)

register()
```

### Testing

Each adapter should include comprehensive tests:

```bash
cd datus-<database>
pytest tests/
```

### Publishing

```bash
# Build
python -m build

# Publish to PyPI
python -m twine upload dist/*
```

---

## Using with Datus Agent

Adapters are automatically discovered via entry points:

```yaml
# config.yaml
database:
  type: mysql  # or snowflake, starrocks, etc.
  host: localhost
  port: 3306
  username: root
  password: password
  database: mydb
```

Datus Agent will automatically load the corresponding adapter.

---

## Benefits

### 1. Install on Demand
Users only install the database adapters they need, avoiding unnecessary dependencies.

```bash
# Only use MySQL
pip install datus-agent datus-mysql

# Use MySQL and Snowflake
pip install datus-agent datus-mysql datus-snowflake
```

### 2. Independent Version Management
Each adapter can be published and upgraded independently without affecting the core package.

### 3. Zero Dependency Conflicts
Dependencies for different databases don't interfere with each other.

### 4. Community Contributions
Community can independently develop and publish adapters without waiting for core team review.

### 5. Lightweight Core
Core package reduced from 200MB to 20MB (-90%).

---

## Contributing

Contributions of new database adapters are welcome!

1. Fork this repository
2. Create a new adapter package
3. Add tests and documentation
4. Submit a Pull Request

---

## License

Apache License 2.0

---

## Documentation

- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [StarRocks Implementation](STARROCKS_IMPLEMENTATION.md)
- [Snowflake Implementation](SNOWFLAKE_IMPLEMENTATION.md)
- [Refactoring Plan](connector_refactoring_plan.md)

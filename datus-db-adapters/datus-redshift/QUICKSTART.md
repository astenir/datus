# Redshift Adapter - Quick Start Guide

This guide will help you quickly set up and test the Redshift adapter for Datus Agent.

## 📋 Prerequisites

Before you begin, make sure you have:

1. **Python 3.8 or higher** installed
2. **A Redshift cluster** running and accessible
3. **Credentials** for your Redshift cluster (username and password)
4. **Network access** to your Redshift cluster (check security groups)

## 🚀 Installation

### Step 1: Navigate to the adapter directory

```bash
cd /Users/vijay/Movies/Datus-adapters/datus-redshift
```

### Step 2: Install the adapter

Install in development mode (recommended for testing):

```bash
pip install -e .
```

Or install normally:

```bash
pip install .
```

This will automatically install all required dependencies:
- `datus-agent>=0.2.2`
- `redshift_connector>=2.0.0`
- `pyarrow` (via datus-agent)
- `pandas` (via datus-agent)

## ✅ Verify Installation

After installation, verify that the adapter is working:

```bash
python -c "from datus_redshift import RedshiftConnector, RedshiftConfig; print('✓ Redshift adapter installed successfully!')"
```

## 🧪 Test the Adapter

### Option 1: Using the Example Script

1. **Edit the example script** with your credentials:

```bash
# Open the example script in your editor
nano example_usage.py  # or vim, code, etc.
```

2. **Update the configuration section** (around line 20):

```python
config = RedshiftConfig(
    host="your-cluster.abc123.us-west-2.redshift.amazonaws.com",
    username="your_username",
    password="your_password",
    database="dev",
    schema="public",
    port=5439,
    ssl=True
)
```

3. **Run the example script**:

```bash
python example_usage.py
```

If successful, you should see output showing:
- ✓ Connection test
- ✓ List of databases
- ✓ List of schemas
- ✓ List of tables
- ✓ Query execution results

### Option 2: Using Python Interactively

Start a Python session and try the adapter:

```python
from datus_redshift import RedshiftConnector, RedshiftConfig

# Create configuration
config = RedshiftConfig(
    host="your-cluster.abc123.us-west-2.redshift.amazonaws.com",
    username="your_username",
    password="your_password",
    database="dev"
)

# Create connector
connector = RedshiftConnector(config)

# Test connection
print(connector.test_connection())

# Try a simple query
result = connector.execute_query("SELECT 1")
print(result.sql_return)

# Clean up
connector.close()
```

### Option 3: Using Environment Variables

Set environment variables for testing:

```bash
export REDSHIFT_HOST="your-cluster.region.redshift.amazonaws.com"
export REDSHIFT_USERNAME="your_username"
export REDSHIFT_PASSWORD="your_password"
export REDSHIFT_DATABASE="dev"
```

Then run the tests:

```bash
pytest tests/test_connector.py -v
```

## 📝 Code Structure Overview

Here's what each file does:

### `datus_redshift/config.py`
- **Purpose**: Defines `RedshiftConfig` class for connection configuration
- **Key Features**:
  - Required fields: `host`, `username`, `password`
  - Optional fields: `port`, `database`, `schema`, `ssl`, `iam`, etc.
  - Uses Pydantic for validation
  - Supports both password and IAM authentication

### `datus_redshift/connector.py`
- **Purpose**: Main connector implementation (`RedshiftConnector` class)
- **Key Features**:
  - Inherits from `BaseSqlConnector`, `SchemaNamespaceMixin`, `MaterializedViewSupportMixin`
  - Implements all required database operations
  - Supports multiple result formats (CSV, pandas, Arrow, list)
  - Comprehensive error handling
  - Methods for metadata retrieval (databases, schemas, tables, views, etc.)

### `datus_redshift/__init__.py`
- **Purpose**: Module initialization and registration
- **Key Features**:
  - Exports `RedshiftConnector` and `RedshiftConfig`
  - Auto-registers connector with Datus when imported
  - Defines module version

### `tests/test_connector.py`
- **Purpose**: Unit tests for the connector
- **Key Features**:
  - Tests configuration creation
  - Tests connection and queries
  - Tests metadata retrieval
  - Tests different result formats
  - Tests error handling

## 🔧 Common Issues and Solutions

### Issue 1: Connection Timeout

**Error**: "Connection timed out" or "Could not connect to server"

**Solutions**:
1. Check that your Redshift cluster is running
2. Verify your security group allows inbound connections on port 5439
3. Ensure your IP is whitelisted in the cluster's VPC security group
4. Try increasing `timeout_seconds` in the config

### Issue 2: Authentication Failed

**Error**: "Invalid username or password"

**Solutions**:
1. Verify your credentials are correct
2. Check if the user has permission to access the database
3. Try connecting with a different database tool (e.g., psql) to verify credentials

### Issue 3: SSL Error

**Error**: "SSL error" or "Certificate verification failed"

**Solutions**:
1. Try setting `ssl=False` in the config (only for testing, not recommended for production)
2. Update your SSL certificates
3. Check your network proxy settings

### Issue 4: Import Error

**Error**: "No module named 'datus_redshift'" or "No module named 'redshift_connector'"

**Solutions**:
1. Make sure you installed the package: `pip install -e .`
2. Check you're using the correct Python environment
3. Verify installation: `pip list | grep datus-redshift`

## 📚 Next Steps

Once the adapter is working:

1. **Integrate with Datus Agent**: The adapter is automatically registered and can be used with Datus Agent

2. **Use in your code**:
```python
from datus.tools.db_tools import get_connector

connector = get_connector(
    dialect="redshift",
    config={
        "host": "your-cluster.region.redshift.amazonaws.com",
        "username": "your_username",
        "password": "your_password"
    }
)
```

3. **Explore the API**: See `README.md` for complete API documentation

4. **Run the full test suite**:
```bash
pytest tests/ -v --cov=datus_redshift --cov-report=html
```

## 💡 Key Methods Explained

### Connection Methods
- `test_connection()`: Verify connection works
- `close()`: Close the connection
- `get_type()`: Returns "redshift"

### Query Execution Methods
- `execute_query(sql, result_format)`: Execute any query with specified format
- `execute_arrow(sql)`: Execute and return Arrow table (best for large datasets)
- `execute_pandas(sql)`: Execute and return pandas DataFrame
- `execute_csv(sql)`: Execute and return CSV string
- `execute_insert(sql)`: Execute INSERT statement
- `execute_update(sql)`: Execute UPDATE statement
- `execute_delete(sql)`: Execute DELETE statement
- `execute_ddl(sql)`: Execute DDL statements (CREATE, ALTER, DROP, etc.)

### Metadata Methods
- `get_databases()`: List all databases
- `get_schemas()`: List all schemas
- `get_tables(schema_name)`: List tables in a schema
- `get_views(schema_name)`: List views in a schema
- `get_materialized_views(schema_name)`: List materialized views
- `get_schema(schema_name, table_name)`: Get column information for a table
- `get_tables_with_ddl()`: Get tables with their DDL definitions
- `get_sample_rows(tables, top_n)`: Get sample data from tables

### Context Management
- `do_switch_context(schema_name)`: Switch to a different schema

## 🎯 Testing Checklist

Use this checklist to verify your adapter is working correctly:

- [ ] Installation completes without errors
- [ ] Can import `RedshiftConnector` and `RedshiftConfig`
- [ ] Can create a config object
- [ ] Can create a connector instance
- [ ] Connection test passes
- [ ] Can list databases
- [ ] Can list schemas
- [ ] Can list tables
- [ ] Can execute simple SELECT query
- [ ] Can get table schema information
- [ ] Can execute query with different formats (CSV, pandas, Arrow, list)
- [ ] Error handling works (try invalid SQL)
- [ ] Connection closes properly

## 📧 Support

If you encounter issues:

1. Check the [main README](README.md) for detailed documentation
2. Review the [test file](tests/test_connector.py) for usage examples
3. Look at the [example script](example_usage.py) for a complete working example
4. Open an issue on the [Datus-adapters GitHub repository](https://github.com/Datus-ai/Datus-adapters)

## 🎉 Success!

If you've completed all the steps above, your Redshift adapter is ready to use with Datus Agent!

You can now:
- Connect to Redshift from Datus Agent
- Execute queries and retrieve results
- Access metadata about your Redshift schema
- Build data pipelines using Datus with Redshift as a source/target


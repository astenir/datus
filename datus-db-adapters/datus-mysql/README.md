# datus-mysql

MySQL database adapter for Datus.

## Installation

```bash
pip install datus-mysql
```

This will automatically install the required dependencies:
- `datus-agent`
- `datus-sqlalchemy`
- `pymysql`

## Usage

The adapter is automatically registered with Datus when installed. Configure your database connection in your Datus configuration:

```yaml
database:
  type: mysql
  host: localhost
  port: 3306
  username: root
  password: your_password
  database: your_database
```

Or use programmatically:

```python
from datus_mysql import MySQLConnector

# Create connector
connector = MySQLConnector(
    host="localhost",
    port=3306,
    user="root",
    password="your_password",
    database="mydb"
)

# Test connection
connector.test_connection()

# Execute query
result = connector.execute_query("SELECT * FROM users LIMIT 10")
print(result.sql_return)

# Get table list
tables = connector.get_tables()
print(f"Tables: {tables}")

# Get table schema
schema = connector.get_schema(table_name="users")
for column in schema:
    print(f"{column['name']}: {column['type']}")
```

## Features

- Full CRUD operations (SELECT, INSERT, UPDATE, DELETE)
- DDL execution (CREATE, ALTER, DROP)
- Metadata retrieval (tables, views, schemas)
- Sample data extraction
- Multiple result formats (pandas, arrow, csv, list)
- Connection pooling and management
- Comprehensive error handling

## Requirements

- Python >= 3.10
- MySQL >= 5.7 or MariaDB >= 10.2
- datus-agent >= 0.3.0
- datus-sqlalchemy >= 0.1.0
- pymysql >= 1.0.0

## License

Apache License 2.0

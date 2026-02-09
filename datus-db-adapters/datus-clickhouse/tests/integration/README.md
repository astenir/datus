# Integration Tests

Integration tests require a real ClickHouse database to validate end-to-end functionality.

## Quick Start

```bash
# Start ClickHouse container
docker-compose up -d

# Create test database
docker exec clickhouse clickhouse-client \
  --user default_user --password default_test \
  -q "CREATE DATABASE IF NOT EXISTS default_test"

# Run integration tests
uv run pytest tests/integration/ -m integration -v

# Stop ClickHouse container
docker-compose down
```

## Setup

### Docker (Recommended)

ClickHouse container is pre-configured in `docker-compose.yml`:
- Image: `clickhouse-server:latest`
- Database: `default_test`
- User: `default_user`
- Port: `8123`
- Password: `default_test`

```bash
# Start and wait for service to be ready
docker-compose up -d
docker-compose ps  # Should show "Up"

# Create test database
docker exec clickhouse clickhouse-client \
  --user default_user --password default_test \
  -q "CREATE DATABASE IF NOT EXISTS default_test"

# Run integration tests
uv run pytest tests/integration/ -m integration -v

# View logs if needed
docker-compose logs clickhouse
```

### Manual Setup (Alternative)

```sql
CREATE DATABASE default_test;
GRANT ALL ON default_test.* TO default_user;
```

Set environment variables:
```bash
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_USER=default_user
export CLICKHOUSE_PASSWORD=default_test
export CLICKHOUSE_DATABASE=default_test
```

## Test Coverage (20 tests)

| Category | Tests | What's Tested |
|----------|-------|---------------|
| Connection | 2 | Config object, dict config |
| Database Ops | 2 | List databases, filter system DBs |
| Table Metadata | 4 | Tables, views, DDL retrieval |
| Schema | 1 | Column info, types, constraints |
| SQL Execution | 5 | SELECT, INSERT, UPDATE, DELETE, DDL |
| Sample Data | 1 | Row sampling |
| Edge Cases | 3 | Special chars, empty results, errors |
| Utilities | 2 | Error handling, connection mgmt |

## Test Pattern

All tests use **dynamic table creation** to avoid conflicts:

```python
@pytest.mark.integration
def test_example(connector, config):
    # Unique table name per test run
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_xxx_{suffix}"

    # Create → Test → Cleanup
    connector.execute_ddl(f"CREATE TABLE {table_name} ...")
    try:
        # Run test
        result = connector.some_operation(table_name)
        assert result.success
    finally:
        # Always cleanup
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
```

## Acceptance Tests

A subset of 6 integration tests are marked as `acceptance` tests for quick validation:
- Connection test
- Database/table operations
- Schema retrieval
- SELECT and DDL execution

Run only acceptance integration tests:
```bash
uv run pytest tests/ -m "acceptance and integration" -v
```

## Troubleshooting

**Tests skipped?**
- Check ClickHouse status: `docker-compose ps`
- Wait for "healthy" status (up to 30s)
- View logs: `docker-compose logs clickhouse`

**Clean slate?**
```bash
# Remove all data
docker-compose down -v
```

## CI/CD

Integration tests run automatically in GitHub Actions with ClickHouse service container.

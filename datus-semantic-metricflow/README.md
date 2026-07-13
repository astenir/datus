# datus-semantic-metricflow

MetricFlow adapter for Datus semantic layer.

## Installation

```bash
pip install datus-semantic-metricflow
```

Dependencies (`datus-metricflow`, `pydantic`) will be installed automatically.

## Requirements

- Python >= 3.12

## Quick Start

```python
import asyncio
from datus_semantic_metricflow import MetricFlowAdapter, MetricFlowConfig

config = MetricFlowConfig(
    datasource="my_project",
    config_path="/path/to/metricflow/config",  # optional
)

adapter = MetricFlowAdapter(config)

async def main():
    # List metrics
    metrics = await adapter.list_metrics(limit=10)
    for metric in metrics:
        print(f"{metric.name}: {metric.description}")

    # Get dimensions for a metric
    dimensions = await adapter.get_dimensions("revenue")
    for dim in dimensions:
        print(f"{dim.name}: {dim.description}")

    # Query metrics
    result = await adapter.query_metrics(
        metrics=["revenue", "orders"],
        dimensions=["date", "region"],
        limit=100,
    )
    print(f"Columns: {result.columns}")
    print(f"Data: {result.data[:5]}")

asyncio.run(main())
```

## Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `datasource` | str | Required | Datasource for this semantic layer instance |
| `config_path` | str | None | Path to MetricFlow configuration file |
| `timeout` | int | 300 | Query timeout in seconds |
| `db_config` | dict | None | Datus datasource config; Snowflake supports password or `private_key` / `private_key_file` with `private_key_file_pwd` plus optional `role`; OceanBase Oracle also passes JDBC jar, driver, connection mode, SSL, and timeout fields to MetricFlow |

### OceanBase Oracle development profile

OceanBase Oracle support requires the matching `datus-metricflow` engine and
the `datus-oceanbase-oracle` database adapter. Until both packages have a
compatible published release, install all three repositories from source; do
not add an unresolved package version to an application lock file.

```python
config = MetricFlowConfig(
    datasource="oceanbase_oracle",
    db_config={
        "type": "oceanbase-oracle",
        "host": "ob.example.com",
        "port": 2883,
        "username": "app@tenant#cluster",
        "password": "...",
        "database": "tenant",
        "schema": "APP",
        "jar_path": "/opt/datus/jars/oceanbase-client.jar",
        "connection_mode": "odp",
        "connect_timeout_seconds": 30,
        "query_timeout_seconds": 60,
    },
    semantic_models_path="/path/to/semantic_models",
)
```

The initial engine profile is read-only. Semantic validation, dry-run SQL and
metric queries are in scope; MetricFlow-managed schema/table writes, query
cancellation and percentile capabilities are not.

## API

- `list_metrics(path=None, limit=100, offset=0)` - List available metrics
- `get_dimensions(metric_name, path=None)` - Get dimensions for a metric
- `query_metrics(metrics, dimensions=[], ...)` - Execute metric queries
- `validate_semantic()` - Validate configuration files

## Development

```bash
pip install -e ".[dev]"
pytest
```

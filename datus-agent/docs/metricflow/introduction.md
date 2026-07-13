# Datus-MetricFlow Introduction

> **Note**: This project is forked from [dbt-labs/metricflow](https://github.com/dbt-labs/metricflow) version 0.140.0 and continues development from there. We are grateful to the dbt Labs team for their excellent work on the original MetricFlow project.

## What is MetricFlow?

MetricFlow is a semantic layer that helps you organize and manage metric definitions in code. It automatically generates clean, reusable SQL queries from your metric definitions, ensuring consistent metric outputs across your organization.

Simply put, MetricFlow allows you to:

- Define your business metrics once in a standardized way
- Query those metrics consistently across different dimensions
- Get automatically generated SQL that's optimized for your data warehouse.

## Key Features

### Metric Management

- **Centralized Definitions**: Define all metrics in one place using simple YAML configuration
- **Multiple Metric Types**: Support for simple metrics, ratios, expressions, and cumulative metrics
- **Dimension Analysis**: Break down metrics by any dimension (time, geography, product category, etc.)

### Smart Query Generation

- **Automatic SQL Generation**: Converts metric requests into optimized SQL queries
- **Multi-hop Joins**: Handles complex joins between fact tables and dimension tables
- **Time Granularity**: Aggregate metrics at different time periods (daily, weekly, monthly, etc.)

### Integration & Flexibility

- **Multiple Data Warehouses**: Works with various data platforms
- **API Integration**: Build custom integrations with downstream tools
- **Version Control**: Manage metric definitions in Git like regular code

## Supported Systems

### Data Warehouses

datus-metricflow currently supports:

- **DuckDB**, **SQLite** - embedded databases for local development and demos
- **MySQL**, **PostgreSQL**, **Greenplum** - relational and analytical databases
- **ClickHouse**, **StarRocks**, **Trino** - analytical engines
- **Snowflake** - cloud data warehouse
- **OceanBase Oracle** - preview read-only profile; requires
  `datus-oceanbase-oracle`, Java, an OceanBase Connector/J jar, and final
  verification against a real Oracle-mode tenant

Database support is not selected only by whether a Python driver or SQLAlchemy
dialect exists. MetricFlow registers a client, SQL renderer, data types, time
functions, row limiting, bind parameters, and a capability profile for each
engine. An unregistered datasource dialect is therefore rejected during
adapter initialization instead of producing incorrect SQL later.

The initial OceanBase Oracle profile supports semantic validation, dry runs,
read-only metric queries, common aggregations and grouping, and
day/week/month/quarter/year time truncation. MetricFlow-managed schema/table
writes, query cancellation, and percentile capabilities are not supported.

## Enhancements in datus-metricflow

Building on MetricFlow 0.140.0, we have made the following improvements:

- **Python 3.12 Support**: Upgraded to support the latest Python version
- **Additional Database Support**: Added Datus-specific SQL clients and renderers, including the preview OceanBase Oracle read-only profile
- **Datus Integration**: Seamlessly integrated with the Datus project for unified configuration
- **Standalone Package**: Can be installed as a dependency and used independently

## Installing datus-metricflow

Make sure you have Python 3.12 installed on your system. Then install via pip:

```bash
pip install datus-metricflow
```

## Next Steps

After installation:

1. **Define Your Metrics**: Create YAML files in the semantic models directory or use subagents to define your business metrics
2. **Query Your Metrics**: Use the `mf query` command or integrate with Datus Agent to query your metrics
3. **Integrate with Tools**: Use the MCP server to connect MetricFlow with LLM applications

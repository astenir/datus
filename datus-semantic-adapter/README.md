# Datus Semantic Adapter

Semantic layer adapters for the Datus platform.

This repository contains adapters that integrate various semantic layer backends with Datus, providing a unified interface for metric discovery, querying, and validation.

## Available Adapters

| Adapter | Package | Description |
|---------|---------|-------------|
| MetricFlow | `datus-semantic-metricflow` | MetricFlow semantic layer integration |

## Architecture

All adapters implement the `BaseSemanticAdapter` interface from `datus-agent`, providing:

- Metric listing and discovery
- Dimension querying
- Metric query execution
- Configuration validation

## Installation

Each adapter is published as a separate package:

```bash
pip install datus-semantic-metricflow
```

See individual adapter READMEs for detailed usage instructions.

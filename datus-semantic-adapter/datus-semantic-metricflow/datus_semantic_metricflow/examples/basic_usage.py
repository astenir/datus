"""
Basic usage example for datus-metricflow adapter.

This example demonstrates how to:
1. Configure and create a MetricFlow adapter
2. List available metrics
3. Get dimensions for a metric
4. Query metrics with filters
5. Validate the semantic layer
"""

import asyncio
from datus_semantic_metricflow import (
    MetricFlowAdapter,
    MetricFlowConfig,
    TimeRange,
    TimeGranularity,
)


async def main():
    # Configure the adapter
    config = MetricFlowConfig(
        datasource="my_project",
        project_root="/path/to/your/metricflow/project",
        cli_path="mf",  # or "/path/to/mf" if not in PATH
    )

    # Create adapter instance
    adapter = MetricFlowAdapter(config)

    print("=" * 60)
    print("MetricFlow Adapter Example")
    print("=" * 60)

    # 1. List available metrics
    print("\n1. Listing available metrics...")
    try:
        metrics = await adapter.list_metrics(limit=5)
        print(f"Found {len(metrics)} metrics:")
        for metric in metrics:
            print(f"  - {metric.name}: {metric.description or 'No description'}")
    except Exception as e:
        print(f"Error listing metrics: {e}")

    # 2. Get dimensions for a metric
    print("\n2. Getting dimensions for a metric...")
    try:
        metric_name = "revenue"  # Change this to an actual metric in your project
        dimensions = await adapter.get_dimensions(metric_name)
        print(f"Dimensions for '{metric_name}':")
        for dim in dimensions:
            print(f"  - {dim}")
    except Exception as e:
        print(f"Error getting dimensions: {e}")

    # 3. Query metrics
    print("\n3. Querying metrics...")
    try:
        result = await adapter.query_metrics(
            metrics=["revenue"],  # Change to your actual metrics
            dimensions=["date"],  # Change to your actual dimensions
            limit=10,
        )
        print(f"Columns: {result.columns}")
        print(f"First 5 rows:")
        for row in result.data[:5]:
            print(f"  {row}")
    except Exception as e:
        print(f"Error querying metrics: {e}")

    # 4. Query with time range
    print("\n4. Querying with time range...")
    try:
        result = await adapter.query_metrics(
            metrics=["revenue"],
            dimensions=["date"],
            time_range=TimeRange(
                start="2024-01-01",
                end="2024-12-31",
                granularity=TimeGranularity.MONTH,
            ),
            limit=12,
        )
        print(f"Monthly data points: {len(result.data)}")
    except Exception as e:
        print(f"Error querying with time range: {e}")

    # 5. Dry run (explain query)
    print("\n5. Dry run (explain query)...")
    try:
        result = await adapter.query_metrics(
            metrics=["revenue"],
            dimensions=["date", "region"],
            dry_run=True,
        )
        print("Generated SQL:")
        print(result.data[0][0] if result.data else "No SQL generated")
    except Exception as e:
        print(f"Error in dry run: {e}")

    # 6. Validate semantic layer
    print("\n6. Validating semantic layer configuration...")
    try:
        validation = await adapter.validate_semantic()
        if validation.valid:
            print("Configuration is valid!")
        else:
            print(f"Found {len(validation.issues)} issues:")
            for issue in validation.issues:
                print(f"  [{issue.severity}] {issue.message}")
    except Exception as e:
        print(f"Error validating: {e}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

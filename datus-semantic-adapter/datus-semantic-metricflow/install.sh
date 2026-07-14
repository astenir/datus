#!/bin/bash
# Installation script for datus-semantic-metricflow

set -e

echo "Installing datus-semantic-metricflow with metricflow submodule..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Must run this script from datus-semantic-metricflow directory"
    exit 1
fi

# Install metricflow from submodule first
if [ -d "metricflow" ]; then
    echo "Step 1: Installing metricflow from submodule..."
    pip install -e metricflow
else
    echo "Error: metricflow submodule not found. Run: git submodule update --init --recursive"
    exit 1
fi

# Install this package
echo "Step 2: Installing datus-semantic-metricflow..."
pip install -e .

echo "✅ Installation complete!"
echo ""
echo "Test with:"
echo "  python -c 'from metricflow.api.metricflow_client import MetricFlowClient; print(\"✅ MetricFlow OK\")'"
echo "  python -c 'from datus_semantic_metricflow import MetricFlowAdapter; print(\"✅ Adapter OK\")'"

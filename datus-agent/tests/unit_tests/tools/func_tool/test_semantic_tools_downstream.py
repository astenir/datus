"""Downstream relative-time and OceanBase Oracle semantic coverage."""

from unittest.mock import Mock, patch

import pytest

from datus.configuration.agent_config import AgentConfig, NodeConfig
from datus.tools.func_tool.semantic_tools import SemanticTools
from datus.tools.semantic_tools.models import QueryResult


@pytest.fixture
def semantic_tools():
    with (
        patch("datus.tools.func_tool.semantic_tools.SemanticModelRAG"),
        patch("datus.tools.func_tool.semantic_tools.MetricRAG"),
    ):
        config = Mock()
        config.active_model.return_value.model = "gpt-4o"
        config.resolve_semantic_adapter.side_effect = lambda adapter_type=None: adapter_type
        config.build_semantic_adapter_config.side_effect = lambda adapter_type=None: {"datasource": "ns1"}
        return SemanticTools(agent_config=config, adapter_type="mock_adapter")


@pytest.fixture
def mock_adapter(semantic_tools):
    adapter = Mock()
    semantic_tools._adapter = adapter
    return adapter


@pytest.mark.parametrize("dry_run", [False, True])
def test_query_metrics_resolves_relative_time_before_adapter_call(semantic_tools, mock_adapter, dry_run):
    query_result = QueryResult(columns=["x"], data=[{"x": 1}], metadata={})
    semantic_tools._reference_date_provider = lambda: "2026-07-16"

    with patch("datus.tools.func_tool.semantic_tools._run_async", return_value=query_result):
        result = semantic_tools.query_metrics(
            metrics=["free_meal_count_ages_5_17_rate"],
            time_start="-10y",
            time_end="now",
            dry_run=dry_run,
        )

    assert result.success == 1
    mock_adapter.query_metrics.assert_called_once_with(
        metrics=["free_meal_count_ages_5_17_rate"],
        dimensions=[],
        path=None,
        time_start="2016-07-16",
        time_end="2026-07-16",
        time_granularity=None,
        where=None,
        limit=None,
        order_by=None,
        dry_run=dry_run,
    )


@pytest.mark.parametrize(
    "relative_time, reference_date, expected",
    [
        ("-10d", "2026-07-16", "2026-07-06"),
        ("-2w", "2026-07-16", "2026-07-02"),
        ("-3m", "2026-07-31", "2026-04-30"),
        ("-1y", "2024-02-29", "2023-02-28"),
    ],
)
def test_query_metrics_resolves_relative_time_with_calendar_boundaries(
    semantic_tools,
    mock_adapter,
    relative_time,
    reference_date,
    expected,
):
    query_result = QueryResult(columns=["x"], data=[{"x": 1}], metadata={})
    semantic_tools._reference_date_provider = lambda: reference_date

    with patch("datus.tools.func_tool.semantic_tools._run_async", return_value=query_result):
        result = semantic_tools.query_metrics(metrics=["revenue"], time_start=relative_time)

    assert result.success == 1
    assert mock_adapter.query_metrics.call_args.kwargs["time_start"] == expected


def test_query_metrics_rejects_invalid_relative_time_before_adapter_call(semantic_tools, mock_adapter):
    result = semantic_tools.query_metrics(metrics=["revenue"], time_start="-10years")

    assert result.success == 0
    assert "time_start must be an ISO date/timestamp or a relative value" in result.error
    mock_adapter.query_metrics.assert_not_called()


def test_metricflow_adapter_initializes_for_oceanbase_oracle(tmp_path, monkeypatch):
    import datus_oceanbase_oracle

    monkeypatch.setenv("HOME", str(tmp_path))
    connector = Mock()
    connector_factory = Mock(return_value=connector)
    monkeypatch.setattr(datus_oceanbase_oracle, "OceanBaseOracleConnector", connector_factory)
    config = AgentConfig(
        nodes={"test": NodeConfig(model="test-model", input=None)},
        home=str(tmp_path / "h"),
        target="mock",
        models={
            "mock": {
                "type": "openai",
                "api_key": "k",
                "model": "m",
                "base_url": "http://localhost:0",
            }
        },
        services={
            "datasources": {
                "ob_oracle": {
                    "type": "oceanbase-oracle",
                    "host": "ob.example.com",
                    "port": "2883",
                    "username": "app@tenant#cluster",
                    "password": "secret",
                    "database": "tenant",
                    "schema": "APP",
                    "jar_path": "/opt/oceanbase-client.jar",
                    "default": True,
                },
            },
            "semantic_layer": {"metricflow": {"datasource": "ob_oracle"}},
        },
        skip_init_dirs=True,
    )

    with (
        patch("datus.tools.func_tool.semantic_tools.SemanticModelRAG"),
        patch("datus.tools.func_tool.semantic_tools.MetricRAG"),
    ):
        tool = SemanticTools(
            agent_config=config,
            adapter_type="metricflow",
            runtime_db_context_provider=lambda: {
                "datasource": "ob_oracle",
                "database": "tenant",
                "schema": "APP",
            },
        )
        adapter = tool.adapter

    assert adapter is not None
    assert tool._adapter_load_error is None
    assert adapter.client.sql_client.sql_engine_attributes.sql_engine_type.value == "OceanBase Oracle"
    connector_factory.assert_called_once()
    connector_config = connector_factory.call_args.args[0]
    assert connector_config["jar_path"] == "/opt/oceanbase-client.jar"
    assert connector_config["schema"] == "APP"

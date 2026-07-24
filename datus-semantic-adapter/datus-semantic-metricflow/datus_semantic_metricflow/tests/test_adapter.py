from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from metricflow.time.time_granularity import TimeGranularity

from datus_semantic_metricflow import MetricFlowAdapter, MetricFlowConfig
from datus_semantic_metricflow.adapter import MetricFlowSemanticValidationException
from datus_semantic_metricflow.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    ValidationIssue,
    ValidationResult,
)


def _build_config_without_sslmode(
    db_type="",
    host="",
    port="",
    username="",
    password="",
    database="",
    schema="",
    uri="",
    warehouse="",
    account="",
    project_id="",
    model_path="",
):
    _build_config_without_sslmode.calls.append(
        {
            "db_type": db_type,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database,
            "schema": schema,
            "uri": uri,
            "warehouse": warehouse,
            "account": account,
            "project_id": project_id,
            "model_path": model_path,
        }
    )
    return {"k": "v"}


_build_config_without_sslmode.calls = []


def _build_config_with_sslmode(
    db_type="",
    host="",
    port="",
    username="",
    password="",
    database="",
    schema="",
    uri="",
    warehouse="",
    account="",
    project_id="",
    model_path="",
    sslmode="",
):
    _build_config_with_sslmode.calls.append(
        {
            "db_type": db_type,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database,
            "schema": schema,
            "uri": uri,
            "warehouse": warehouse,
            "account": account,
            "project_id": project_id,
            "model_path": model_path,
            "sslmode": sslmode,
        }
    )
    return {"k": "v"}


_build_config_with_sslmode.calls = []


def _build_config_from_datus_datasource(db_config, model_path=""):
    _build_config_from_datus_datasource.calls.append(
        {
            "db_config": dict(db_config),
            "model_path": model_path,
        }
    )
    return {"k": "v"}


_build_config_from_datus_datasource.calls = []


class _FakeColumns(list):
    def tolist(self):
        return list(self)


class _FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows
        self.empty = not rows
        self.columns = _FakeColumns(list(rows[0].keys()) if rows else [])

    def to_dict(self, orient="records"):
        assert orient == "records"
        return list(self._rows)


def _validation_results(*, errors=None, warnings=None, has_blocking_issues=False):
    return SimpleNamespace(
        errors=list(errors or []),
        warnings=list(warnings or []),
        has_blocking_issues=has_blocking_issues,
    )


class UnableToSatisfyQueryError(Exception):
    """Stand-in matching MetricFlow's query validation exception by class name."""


def _metricflow_metric(
    name,
    metric_type,
    *,
    window=None,
    grain_to_date=None,
    input_metrics=None,
):
    return SimpleNamespace(
        name=name,
        description=name,
        type=metric_type,
        input_measures=[],
        input_metrics=input_metrics or [],
        type_params=SimpleNamespace(
            expr=None,
            metrics=input_metrics or [],
            window=window,
            grain_to_date=grain_to_date,
            measure=None,
            numerator=None,
            denominator=None,
        ),
    )


@pytest.fixture
def config():
    return MetricFlowConfig(datasource="test", timeout=300)


@pytest.fixture
def adapter():
    instance = MetricFlowAdapter.__new__(MetricFlowAdapter)
    instance.service_type = "metricflow"
    instance.datasource = "test"
    instance.timeout = 300
    instance.client = MagicMock()
    instance._client_initialized = True
    instance._config_handler = MagicMock()
    return instance


class TestMetricFlowAdapterAuthoringCacheInvalidation:
    """A successful authoring mutation must drop the cached client so later
    reads (list_metrics / query_metrics / get_dimensions) reload the YAML."""

    def test_write_metric_source_invalidates_client_cache(self, adapter):
        adapter._author = lambda: SimpleNamespace(write=lambda *a, **k: SimpleNamespace(name="m"))
        adapter._client_initialized = True
        adapter.write_metric_source("m", "metric:\n  name: m\n  type: aggregate\n")
        assert adapter._client_initialized is False

    def test_delete_metric_source_invalidates_client_cache(self, adapter):
        adapter._author = lambda: SimpleNamespace(delete=lambda *a, **k: SimpleNamespace(name="m"))
        adapter._client_initialized = True
        adapter.delete_metric_source("m")
        assert adapter._client_initialized is False


class TestMetricFlowAdapter:
    def test_resolve_model_path_uses_agent_home_and_datasource(self):
        config = MetricFlowConfig(datasource="analytics", agent_home="/tmp/datus-home")

        result = MetricFlowAdapter._resolve_model_path(config)

        assert result.endswith("/tmp/datus-home/semantic_models/analytics")

    def test_resolve_model_path_honors_explicit_semantic_models_path(self, tmp_path):
        semantic_models_path = tmp_path / "semantic" / "models"
        config = MetricFlowConfig(
            datasource="analytics",
            agent_home="/tmp/datus-home",
            semantic_models_path=str(semantic_models_path),
        )

        result = MetricFlowAdapter._resolve_model_path(config)

        assert result == str(semantic_models_path)
        assert semantic_models_path.is_dir()

    def test_build_metricflow_config_dict_uses_datus_datasource_builder(self):
        _build_config_from_datus_datasource.calls.clear()

        with patch(
            "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource",
            _build_config_from_datus_datasource,
        ):
            result = MetricFlowAdapter._build_metricflow_config_dict(
                {
                    "type": "snowflake",
                    "account": "sf_account",
                    "username": "sf_user",
                    "database": "sf_db",
                    "warehouse": "wh1",
                    "private_key": "inline-private-key",
                    "private_key_file_pwd": 1234,
                },
                "/tmp/models",
            )

        assert result == {"k": "v"}
        assert _build_config_from_datus_datasource.calls == [
            {
                "db_config": {
                    "type": "snowflake",
                    "account": "sf_account",
                    "username": "sf_user",
                    "database": "sf_db",
                    "warehouse": "wh1",
                    "private_key": "inline-private-key",
                    "private_key_file_pwd": 1234,
                },
                "model_path": "/tmp/models",
            }
        ]

    def test_build_metricflow_config_dict_preserves_oceanbase_oracle_jdbc_fields(self):
        result = MetricFlowAdapter._build_metricflow_config_dict(
            {
                "type": "oceanbase-oracle",
                "host": "ob.example.com",
                "port": "2883",
                "username": "app@tenant#cluster",
                "password": "secret",
                "database": "tenant",
                "schema": "APP",
                "jar_path": "/opt/oceanbase-client.jar",
                "driver_class": "com.oceanbase.jdbc.Driver",
                "connection_mode": "odp",
                "use_ssl": "false",
                "connect_timeout_seconds": "15",
                "query_timeout_seconds": "45",
            },
            "/tmp/models",
        )

        assert result["dwh_dialect"] == "oceanbase-oracle"
        assert result["dwh_jar_path"] == "/opt/oceanbase-client.jar"
        assert result["dwh_driver_class"] == "com.oceanbase.jdbc.Driver"
        assert result["dwh_connection_mode"] == "odp"
        assert result["dwh_use_ssl"] == "false"
        assert result["dwh_connect_timeout_seconds"] == "15"
        assert result["dwh_query_timeout_seconds"] == "45"

    def test_build_metricflow_config_dict_legacy_normalizes_db_config(self):
        captured_kwargs = {}

        def fake_build_config_dict_from_db_params(**kwargs):
            captured_kwargs.update(kwargs)
            return {"config": "ok"}

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                fake_build_config_dict_from_db_params,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
        ):
            result = MetricFlowAdapter._build_metricflow_config_dict(
                {
                    "type": "postgres",
                    "host": "localhost",
                    "port": 15432,
                    "username": "datus",
                    "password": "secret",
                    "database": "analytics",
                    "schema": "public",
                    "sslmode": "require",
                },
                "/tmp/models",
            )

        assert result == {"config": "ok"}
        assert captured_kwargs == {
            "db_type": "postgres",
            "host": "localhost",
            "port": "15432",
            "username": "datus",
            "password": "secret",
            "database": "analytics",
            "schema": "public",
            "uri": "",
            "warehouse": "",
            "account": "",
            "project_id": "",
            "model_path": "/tmp/models",
            "sslmode": "require",
        }

    def test_build_metricflow_config_dict_legacy_forwards_runtime_context_aliases(self):
        captured_kwargs = {}

        def fake_build_config_dict_from_db_params(**kwargs):
            captured_kwargs.update(kwargs)
            return {"config": "ok"}

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                fake_build_config_dict_from_db_params,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
        ):
            result = MetricFlowAdapter._build_metricflow_config_dict(
                {
                    "type": "trino",
                    "host": "trino-host",
                    "database_name": "college_exam",
                    "db_schema": "college_exam_schema",
                    "catalog_name": "hive",
                },
                "/tmp/models",
            )

        assert result == {"config": "ok"}
        assert captured_kwargs["database"] == "college_exam"
        assert captured_kwargs["schema"] == "college_exam_schema"
        assert captured_kwargs["catalog"] == "hive"

    def test_build_metricflow_config_dict_legacy_forwards_snowflake_key_pair_fields(self):
        captured_kwargs = {}

        def fake_build_config_dict_from_db_params(**kwargs):
            captured_kwargs.update(kwargs)
            return {"config": "ok"}

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                fake_build_config_dict_from_db_params,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
        ):
            result = MetricFlowAdapter._build_metricflow_config_dict(
                {
                    "type": "snowflake",
                    "account": "sf_account",
                    "username": "sf_user",
                    "database": "sf_db",
                    "schema": "public",
                    "warehouse": "wh1",
                    "role": "analyst",
                    "private_key": "inline-private-key",
                    "private_key_file": "/tmp/rsa_key.p8",
                    "private_key_file_pwd": 1234,
                },
                "/tmp/models",
            )

        assert result == {"config": "ok"}
        assert captured_kwargs["password"] == ""
        assert captured_kwargs["role"] == "analyst"
        assert captured_kwargs["private_key"] == "inline-private-key"
        assert captured_kwargs["private_key_file"] == "/tmp/rsa_key.p8"
        assert captured_kwargs["private_key_file_pwd"] == "1234"

    def test_build_metricflow_config_dict_rejects_snowflake_key_pair_fields_when_unsupported(self):
        _build_config_with_sslmode.calls.clear()

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                _build_config_with_sslmode,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
        ):
            with pytest.raises(
                RuntimeError, match="does not support Snowflake config fields: private_key_file"
            ):
                MetricFlowAdapter._build_metricflow_config_dict(
                    {
                        "type": "snowflake",
                        "account": "sf_account",
                        "username": "sf_user",
                        "database": "sf_db",
                        "warehouse": "wh1",
                        "private_key_file": "/tmp/rsa_key.p8",
                    },
                    "/tmp/models",
                )

        assert _build_config_with_sslmode.calls == []

    def test_collect_model_file_paths_includes_gitignored_yaml(self, tmp_path):
        (tmp_path / ".gitignore").write_text("/subject/\n")
        model_dir = tmp_path / "subject" / "semantic_models" / "analytics"
        model_dir.mkdir(parents=True)
        yaml_file = model_dir / "orders.yml"
        yaml_file.write_text("data_source:\n  name: orders\n")
        hidden_file = model_dir / ".ignored.yml"
        hidden_file.write_text("data_source:\n  name: ignored\n")
        non_yaml_file = model_dir / "notes.txt"
        non_yaml_file.write_text("ignored")

        result = MetricFlowAdapter._collect_model_file_paths(str(model_dir))

        assert result == [str(yaml_file)]

    def test_init_uses_dict_config_handler_when_db_config_present_and_sslmode_supported(self):
        mock_handler = MagicMock()
        mock_handler.get_value.return_value = "datus_system"
        mock_sql_client = MagicMock()
        mock_user_model = MagicMock()
        mock_client = MagicMock()
        _build_config_with_sslmode.calls.clear()

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                _build_config_with_sslmode,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
            patch(
                "datus_semantic_metricflow.adapter.DictConfigHandler",
                return_value=mock_handler,
            ) as mock_dict_handler,
            patch(
                "datus_semantic_metricflow.adapter.MetricFlowClient", return_value=mock_client
            ) as mock_client_cls,
            patch(
                "metricflow.sql_clients.sql_utils.make_sql_client_from_config",
                return_value=mock_sql_client,
            ),
            patch.object(
                MetricFlowAdapter,
                "_build_user_configured_model_from_config",
                return_value=mock_user_model,
            ),
            patch("metricflow.configuration.constants.CONFIG_DWH_SCHEMA", "datus_system"),
            patch.object(MetricFlowAdapter, "_resolve_model_path", return_value="/tmp/models"),
        ):
            adapter = MetricFlowAdapter(
                MetricFlowConfig(
                    datasource="test",
                    db_config={"type": "greenplum", "database": "demo", "sslmode": "disable"},
                    agent_home="/tmp/home",
                )
            )

        assert len(_build_config_with_sslmode.calls) == 1
        assert _build_config_with_sslmode.calls[0]["sslmode"] == "disable"
        mock_dict_handler.assert_called_once_with({"k": "v"})
        mock_client_cls.assert_not_called()
        assert adapter.client.sql_client is mock_sql_client
        assert adapter.client.system_schema == "datus_system"
        assert adapter._client_initialized is False

    def test_init_omits_sslmode_when_metricflow_config_builder_does_not_support_it(self):
        mock_handler = MagicMock()
        mock_handler.get_value.return_value = "datus_system"
        mock_sql_client = MagicMock()
        mock_client = MagicMock()
        _build_config_without_sslmode.calls.clear()

        with (
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_db_params",
                _build_config_without_sslmode,
            ),
            patch(
                "datus_semantic_metricflow.adapter.build_config_dict_from_datus_datasource", None
            ),
            patch(
                "datus_semantic_metricflow.adapter.DictConfigHandler",
                return_value=mock_handler,
            ) as mock_dict_handler,
            patch(
                "datus_semantic_metricflow.adapter.MetricFlowClient", return_value=mock_client
            ) as mock_client_cls,
            patch(
                "metricflow.sql_clients.sql_utils.make_sql_client_from_config",
                return_value=mock_sql_client,
            ),
            patch.object(
                MetricFlowAdapter,
                "_build_user_configured_model_from_config",
                return_value=MagicMock(),
            ),
            patch("metricflow.configuration.constants.CONFIG_DWH_SCHEMA", "datus_system"),
            patch.object(MetricFlowAdapter, "_resolve_model_path", return_value="/tmp/models"),
        ):
            adapter = MetricFlowAdapter(
                MetricFlowConfig(
                    datasource="test",
                    db_config={"type": "greenplum", "database": "demo", "sslmode": "disable"},
                    agent_home="/tmp/home",
                )
            )

        assert len(_build_config_without_sslmode.calls) == 1
        assert "sslmode" not in _build_config_without_sslmode.calls[0]
        mock_dict_handler.assert_called_once_with({"k": "v"})
        mock_client_cls.assert_not_called()
        assert adapter.client.sql_client is mock_sql_client
        assert adapter.client.system_schema == "datus_system"
        assert adapter._client_initialized is False

    def test_init_uses_file_config_handler_when_db_config_missing(self):
        mock_handler = MagicMock()
        mock_client = MagicMock()

        with (
            patch(
                "datus_semantic_metricflow.adapter.DatusConfigHandler", return_value=mock_handler
            ) as mock_handler_cls,
            patch(
                "datus_semantic_metricflow.adapter.MetricFlowClient", return_value=mock_client
            ) as mock_client_cls,
            patch(
                "metricflow.sql_clients.sql_utils.make_sql_client_from_config",
                return_value=MagicMock(),
            ),
            patch.object(
                MetricFlowAdapter,
                "_build_user_configured_model_from_config",
                return_value=MagicMock(),
            ),
            patch("metricflow.configuration.constants.CONFIG_DWH_SCHEMA", "datus_system"),
        ):
            adapter = MetricFlowAdapter(
                MetricFlowConfig(datasource="test", config_path="/tmp/agent.yml")
            )

        mock_handler_cls.assert_called_once_with(namespace="test", config_path="/tmp/agent.yml")
        mock_client_cls.assert_not_called()
        assert adapter._client_initialized is False

    def test_init_does_not_parse_yaml_so_validation_can_report_yaml_issues(self):
        mock_handler = MagicMock()
        mock_handler.get_value.return_value = "datus_system"
        mock_sql_client = MagicMock()
        parse_error = ValueError("bad yaml")

        with (
            patch(
                "datus_semantic_metricflow.adapter.DatusConfigHandler", return_value=mock_handler
            ),
            patch("datus_semantic_metricflow.adapter.MetricFlowClient") as mock_client_cls,
            patch(
                "metricflow.sql_clients.sql_utils.make_sql_client_from_config",
                return_value=mock_sql_client,
            ),
            patch.object(
                MetricFlowAdapter,
                "_build_user_configured_model_from_config",
                side_effect=parse_error,
            ),
            patch("metricflow.configuration.constants.CONFIG_DWH_SCHEMA", "datus_system"),
        ):
            adapter = MetricFlowAdapter(
                MetricFlowConfig(datasource="test", config_path="/tmp/agent.yml")
            )

        mock_client_cls.assert_not_called()
        assert adapter._client_init_error is None
        assert adapter._client_initialized is False
        assert adapter.client.sql_client is mock_sql_client
        assert adapter.client.system_schema == "datus_system"

    @pytest.mark.asyncio
    async def test_list_metrics_reports_yaml_error_without_breaking_startup(self, adapter):
        adapter._client_initialized = False
        parse_error = ValueError("bad yaml")

        with patch.object(
            adapter, "_build_user_configured_model_from_config", side_effect=parse_error
        ):
            with pytest.raises(RuntimeError, match="MetricFlow semantic configuration is invalid"):
                await adapter.list_metrics()

        assert adapter._client_init_error is parse_error

    def test_ensure_client_ready_initializes_metricflow_client_on_first_use(self, adapter):
        adapter._client_initialized = False
        adapter.client = SimpleNamespace(sql_client="sql-client", system_schema="datus_system")
        user_model = MagicMock()
        mock_client = MagicMock()

        with (
            patch.object(
                adapter, "_build_user_configured_model_from_config", return_value=user_model
            ),
            patch(
                "datus_semantic_metricflow.adapter.MetricFlowClient", return_value=mock_client
            ) as mock_client_cls,
        ):
            result = adapter._ensure_client_ready()

        assert result is mock_client
        assert adapter.client is mock_client
        assert adapter._client_initialized is True
        assert adapter._client_init_error is None
        mock_client_cls.assert_called_once_with(
            sql_client="sql-client",
            user_configured_model=user_model,
            system_schema="datus_system",
        )

    @pytest.mark.asyncio
    async def test_list_metrics_returns_metric_definitions(self, adapter):
        metric1 = SimpleNamespace(
            name="revenue",
            description="Total revenue",
            type="simple",
            input_measures=[SimpleNamespace(name="revenue_measure")],
        )
        metric2 = SimpleNamespace(
            name="orders",
            description="Order count",
            type="simple",
            input_measures=[SimpleNamespace(name="orders_measure")],
        )
        metric_semantics = MagicMock()
        metric_semantics.metric_references = ["revenue", "orders"]
        metric_semantics.get_metrics.return_value = [metric1, metric2]
        adapter.client.semantic_model.metric_semantics = metric_semantics
        adapter.client.engine.simple_dimensions_for_metrics.side_effect = [
            [SimpleNamespace(name="date"), SimpleNamespace(name="region")],
            [SimpleNamespace(name="date")],
        ]

        metrics = await adapter.list_metrics(limit=1, offset=1)

        assert metrics == [
            MetricDefinition(
                name="orders",
                description="Order count",
                type="simple",
                dimensions=["date"],
                measures=["orders_measure"],
                metadata={},
            )
        ]

    @pytest.mark.asyncio
    async def test_list_metrics_includes_derived_offset_metadata(self, adapter):
        metric = SimpleNamespace(
            name="revenue_mom",
            description="Revenue month over month",
            type="derived",
            input_measures=[],
            type_params=SimpleNamespace(
                expr="(revenue - revenue_prev) / NULLIF(revenue_prev, 0)",
                metrics=[
                    SimpleNamespace(name="revenue"),
                    SimpleNamespace(
                        name="revenue",
                        alias="revenue_prev",
                        offset_window=SimpleNamespace(to_string=lambda: "1 month"),
                    ),
                ],
                window=None,
                grain_to_date=None,
                measure=None,
                numerator=None,
                denominator=None,
            ),
        )
        metric_semantics = MagicMock()
        metric_semantics.metric_references = ["revenue_mom"]
        metric_semantics.get_metrics.return_value = [metric]
        adapter.client.semantic_model.metric_semantics = metric_semantics
        adapter.client.engine.simple_dimensions_for_metrics.return_value = [
            SimpleNamespace(name="metric_time")
        ]

        metrics = await adapter.list_metrics()

        assert metrics == [
            MetricDefinition(
                name="revenue_mom",
                description="Revenue month over month",
                type="derived",
                dimensions=["metric_time"],
                measures=[],
                metadata={
                    "expr": "(revenue - revenue_prev) / NULLIF(revenue_prev, 0)",
                    "inputs": [
                        {"name": "revenue"},
                        {"name": "revenue", "alias": "revenue_prev", "offset_window": "1 month"},
                    ],
                    "offset_window": "1 month",
                    "metric_kind": "derived",
                },
            )
        ]

    def test_metric_path_metadata_from_yaml_file_extracts_subject_tree_tags(self, tmp_path):
        metric_file = tmp_path / "metrics.yml"
        metric_file.write_text(
            """
metric:
  name: revenue_mom
  type: derived
  locked_metadata:
    tags:
      - revenue/reporting
      - "subject_tree: commerce/revenue/orders"
  type_params:
    metrics:
      - name: revenue
    expr: revenue
---
metric:
  name: revenue
  type: measure_proxy
  type_params:
    measures:
      - revenue
""",
            encoding="utf-8",
        )

        assert MetricFlowAdapter._metric_path_metadata_from_yaml_file(str(metric_file)) == {
            "revenue_mom": ["commerce", "revenue", "orders"]
        }

    @pytest.mark.asyncio
    async def test_list_metrics_filters_by_locked_metadata_path(self, adapter):
        metric = SimpleNamespace(
            name="revenue_mom",
            description="Revenue month over month",
            type="derived",
            input_measures=[],
            type_params=SimpleNamespace(
                expr="revenue - revenue_prev",
                metrics=[SimpleNamespace(name="revenue")],
                window=None,
                grain_to_date=None,
                measure=None,
                numerator=None,
                denominator=None,
            ),
        )
        metric_semantics = MagicMock()
        metric_semantics.metric_references = ["revenue_mom"]
        metric_semantics.get_metrics.return_value = [metric]
        adapter.client.semantic_model.metric_semantics = metric_semantics
        adapter.client.engine.simple_dimensions_for_metrics.return_value = [
            SimpleNamespace(name="metric_time")
        ]

        with patch.object(
            adapter,
            "_metric_path_metadata_by_name",
            return_value={"revenue_mom": ["commerce", "revenue", "orders"]},
        ):
            metrics = await adapter.list_metrics(path=["commerce", "revenue", "orders"])

        assert len(metrics) == 1
        assert metrics[0].name == "revenue_mom"
        assert metrics[0].path == ["commerce", "revenue", "orders"]

    def test_metricflow_metadata_value_preserves_nested_containers(self):
        value = {
            "constraint": {
                "where": [
                    SimpleNamespace(value="region = 'west'"),
                    SimpleNamespace(name="sales_channel"),
                ]
            },
            "offsets": (SimpleNamespace(to_string=lambda: "1 month"), "1 year"),
        }

        assert MetricFlowAdapter._metricflow_metadata_value(value) == {
            "constraint": {"where": ["region = 'west'", "sales_channel"]},
            "offsets": ["1 month", "1 year"],
        }

    @pytest.mark.asyncio
    async def test_get_dimensions_returns_dimension_info(self, adapter):
        adapter.client.list_dimensions.return_value = [
            SimpleNamespace(name="date", description="Calendar date"),
            SimpleNamespace(name="region", description="Sales region"),
        ]

        dimensions = await adapter.get_dimensions("revenue")

        assert dimensions == [
            DimensionInfo(name="date", description="Calendar date"),
            DimensionInfo(name="region", description="Sales region"),
        ]
        adapter.client.list_dimensions.assert_called_once_with(metric_names=["revenue"])

    @pytest.mark.asyncio
    async def test_query_metrics_returns_rows_as_dicts(self, adapter):
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame(
                [
                    {"date": "2024-01-01", "revenue": 1000},
                    {"date": "2024-01-02", "revenue": 1200},
                ]
            ),
            dataflow_plan="mock-plan",
        )

        result = await adapter.query_metrics(metrics=["revenue"], dimensions=["date"], limit=10)

        assert result == QueryResult(
            columns=["date", "revenue"],
            data=[
                {"date": "2024-01-01", "revenue": 1000},
                {"date": "2024-01-02", "revenue": 1200},
            ],
            metadata={"dataflow_plan": "mock-plan"},
        )
        adapter.client.query.assert_called_once_with(
            metrics=["revenue"],
            dimensions=["date"],
            start_time=None,
            end_time=None,
            where=None,
            limit=10,
            order=None,
        )

    @pytest.mark.asyncio
    async def test_query_metrics_adds_metric_time_dimension_for_granularity(self, adapter):
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(
            metrics=["revenue"],
            dimensions=["region"],
            time_granularity="month",
            order_by=["-revenue", "null"],
        )

        adapter.client.query.assert_called_once_with(
            metrics=["revenue"],
            dimensions=["region", "metric_time__month"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=["-revenue"],
        )

    @pytest.mark.asyncio
    async def test_query_metrics_infers_metric_time_for_cumulative(self, adapter):
        adapter.client.engine._query_parser._time_granularity_solver.local_dimension_granularity_range.return_value = (
            TimeGranularity.DAY,
            TimeGranularity.DAY,
        )
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "running_revenue",
                "cumulative",
                window=SimpleNamespace(to_string=lambda: "1 month"),
            )
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(metrics=["running_revenue"], dimensions=["region"])

        adapter.client.query.assert_called_once_with(
            metrics=["running_revenue"],
            dimensions=["region", "metric_time__day"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=None,
        )

    @pytest.mark.asyncio
    async def test_query_metrics_rejects_cumulative_when_time_grain_resolver_missing(self, adapter):
        adapter.client.engine = SimpleNamespace()
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "running_revenue",
                "cumulative",
                window=SimpleNamespace(to_string=lambda: "1 month"),
            )
        ]

        with pytest.raises(MetricFlowSemanticValidationException) as excinfo:
            await adapter.query_metrics(metrics=["running_revenue"], dimensions=["region"])

        payload = excinfo.value.payload
        assert payload.code == "metricflow_time_grain_resolver_unavailable"
        assert payload.metrics == ["running_revenue"]
        adapter.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_metrics_infers_metric_time_for_offset_derived(self, adapter):
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "revenue_mom",
                "derived",
                input_metrics=[
                    SimpleNamespace(name="revenue"),
                    SimpleNamespace(
                        name="revenue",
                        alias="revenue_prev",
                        offset_window=SimpleNamespace(to_string=lambda: "1 month"),
                    ),
                ],
            )
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(metrics=["revenue_mom"], dimensions=["region"])

        adapter.client.query.assert_called_once_with(
            metrics=["revenue_mom"],
            dimensions=["region", "metric_time__month"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=None,
        )

    @pytest.mark.asyncio
    async def test_query_metrics_uses_one_time_group_for_compatible_metrics(self, adapter):
        adapter.client.engine._query_parser._time_granularity_solver.local_dimension_granularity_range.return_value = (
            TimeGranularity.DAY,
            TimeGranularity.DAY,
        )
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "running_revenue",
                "cumulative",
                window=SimpleNamespace(to_string=lambda: "1 month"),
            ),
            _metricflow_metric(
                "revenue_mom",
                "derived",
                input_metrics=[
                    SimpleNamespace(name="revenue"),
                    SimpleNamespace(
                        name="revenue",
                        alias="revenue_prev",
                        offset_window=SimpleNamespace(to_string=lambda: "1 day"),
                    ),
                ],
            ),
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(
            metrics=["revenue_mom", "running_revenue"], dimensions=["region"]
        )

        adapter.client.query.assert_called_once_with(
            metrics=["revenue_mom", "running_revenue"],
            dimensions=["region", "metric_time__day"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=None,
        )

    @pytest.mark.asyncio
    async def test_query_metrics_rejects_conflicting_required_time_grains(self, adapter):
        adapter.client.engine._query_parser._time_granularity_solver.local_dimension_granularity_range.return_value = (
            TimeGranularity.DAY,
            TimeGranularity.DAY,
        )
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "running_revenue",
                "cumulative",
                window=SimpleNamespace(to_string=lambda: "1 month"),
            ),
            _metricflow_metric(
                "revenue_mom",
                "derived",
                input_metrics=[
                    SimpleNamespace(name="revenue"),
                    SimpleNamespace(
                        name="revenue",
                        alias="revenue_prev",
                        offset_window=SimpleNamespace(to_string=lambda: "1 month"),
                    ),
                ],
            ),
        ]

        with pytest.raises(MetricFlowSemanticValidationException) as excinfo:
            await adapter.query_metrics(
                metrics=["running_revenue", "revenue_mom"],
                dimensions=["region"],
            )

        payload = excinfo.value.payload
        assert payload.code == "metric_time_grain_conflict"
        assert payload.metrics == ["running_revenue", "revenue_mom"]
        adapter.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_metrics_respects_explicit_metric_time_dimension(self, adapter):
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = [
            _metricflow_metric(
                "running_revenue",
                "cumulative",
                grain_to_date=SimpleNamespace(to_string=lambda: "month"),
            )
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(metrics=["running_revenue"], dimensions=["metric_time__day"])

        adapter.client.query.assert_called_once_with(
            metrics=["running_revenue"],
            dimensions=["metric_time__day"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=None,
        )

    @pytest.mark.asyncio
    async def test_query_metrics_maps_metricflow_validation_error(self, adapter):
        adapter.client.semantic_model.metric_semantics.get_metrics.return_value = []
        adapter.client.query.side_effect = UnableToSatisfyQueryError(
            "Metric running_revenue is a cumulative metric specified with a "
            "window/grain_to_date which must be queried with the dimension "
            "'metric_time'."
        )

        with pytest.raises(MetricFlowSemanticValidationException) as excinfo:
            await adapter.query_metrics(metrics=["running_revenue"], dimensions=[])

        payload = excinfo.value.payload
        assert payload.error_type == "semantic_validation_error"
        assert payload.code == "cumulative_requires_metric_time"
        assert payload.required_dimensions == ["metric_time"]
        assert payload.metrics == ["running_revenue"]

    @pytest.mark.asyncio
    async def test_query_metrics_replaces_time_dimension_with_metric_time_granularity(
        self, adapter
    ):
        adapter.client.semantic_model.metric_semantics.element_specs_for_metrics.return_value = [
            SimpleNamespace(
                element_name="order_date",
                qualified_name="order_date",
                time_granularity="day",
                identifier_links=(),
            )
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(
            metrics=["order_count", "gross_order_value"],
            dimensions=["order_date", "order_priority"],
            time_granularity="quarter",
            order_by=["order_date__quarter"],
        )

        adapter.client.query.assert_called_once_with(
            metrics=["order_count", "gross_order_value"],
            dimensions=["order_priority", "metric_time__quarter"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=["metric_time__quarter"],
        )

    @pytest.mark.asyncio
    async def test_query_metrics_canonicalizes_time_alias_without_touching_similar_categorical_name(
        self, adapter
    ):
        adapter.client.semantic_model.metric_semantics.element_specs_for_metrics.return_value = [
            SimpleNamespace(
                element_name="order_date",
                qualified_name="order_date",
                time_granularity="day",
                identifier_links=(),
            )
        ]
        adapter.client.query.return_value = SimpleNamespace(
            result_df=_FakeDataFrame([]), dataflow_plan=None
        )

        await adapter.query_metrics(
            metrics=["order_count"],
            dimensions=["order_date__year", "fiscal_period__month"],
            time_granularity="year",
            order_by=["-order_date__year", "fiscal_period__month"],
        )

        adapter.client.query.assert_called_once_with(
            metrics=["order_count"],
            dimensions=["fiscal_period__month", "metric_time__year"],
            start_time=None,
            end_time=None,
            where=None,
            limit=None,
            order=["-metric_time__year", "fiscal_period__month"],
        )

    @pytest.mark.asyncio
    async def test_query_metrics_dry_run_returns_sql(self, adapter):
        adapter.client.explain.return_value = SimpleNamespace(
            rendered_sql_without_descriptions=SimpleNamespace(sql_query="SELECT 1")
        )

        result = await adapter.query_metrics(metrics=["revenue"], dimensions=["date"], dry_run=True)

        assert result == QueryResult(
            columns=["sql"],
            data=[{"sql": "SELECT 1"}],
            metadata={"explain": True, "sql": "SELECT 1"},
        )
        adapter.client.explain.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_semantic_returns_valid_result(self, adapter):
        adapter.client = SimpleNamespace(sql_client=MagicMock(), system_schema="datus_system")
        lint_results = _validation_results()
        parsing_issues = _validation_results()
        semantic_issues = _validation_results()

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter, "_collect_model_file_paths", return_value=["/tmp/models/orders.yml"]
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model="user-model"),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
            patch("metricflow.model.data_warehouse_model_validator.DataWarehouseModelValidator"),
            patch.object(adapter, "_run_dw_validations", return_value=_validation_results()),
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results
            mock_validator_cls.return_value.validate_model.return_value = SimpleNamespace(
                issues=semantic_issues
            )

            result = await adapter.validate_semantic()

        assert result == ValidationResult(valid=True, issues=[])

    @pytest.mark.asyncio
    async def test_validate_semantic_model_scope_ignores_no_metrics_but_runs_dw(self, adapter):
        adapter.client = SimpleNamespace(sql_client=MagicMock(), system_schema="datus_system")
        lint_results = _validation_results()
        parsing_issues = _validation_results()
        semantic_issues = _validation_results(
            errors=["message='No metrics present in the model.' context=None"],
            has_blocking_issues=True,
        )

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter,
                "_collect_model_file_paths",
                return_value=["/tmp/models/orders.yml"],
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model="user-model"),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
            patch("metricflow.model.data_warehouse_model_validator.DataWarehouseModelValidator"),
            patch.object(
                adapter, "_run_dw_validations", return_value=_validation_results()
            ) as mock_dw,
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results
            mock_validator_cls.return_value.validate_model.return_value = SimpleNamespace(
                issues=semantic_issues
            )

            result = await adapter.validate_semantic(scope="semantic_model")

        assert result == ValidationResult(valid=True, issues=[])
        mock_dw.assert_called_once_with(
            mock_dw.call_args.args[0],
            "user-model",
            include_metrics=False,
        )

    @pytest.mark.asyncio
    async def test_validate_semantic_model_scope_keeps_real_semantic_errors(self, adapter):
        lint_results = _validation_results()
        parsing_issues = _validation_results()
        semantic_issues = _validation_results(
            errors=[
                "message='No metrics present in the model.' context=None",
                "bad time dimension",
            ],
            has_blocking_issues=True,
        )

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter,
                "_collect_model_file_paths",
                return_value=["/tmp/models/orders.yml"],
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model="user-model"),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
            patch.object(adapter, "_run_dw_validations") as mock_dw,
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results
            mock_validator_cls.return_value.validate_model.return_value = SimpleNamespace(
                issues=semantic_issues
            )

            result = await adapter.validate_semantic(scope="semantic_model")

        assert result.valid is False
        assert result.issues == [ValidationIssue(severity="error", message="bad time dimension")]
        mock_dw.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs", [{"scope": ""}, {"validation_scope": ""}])
    async def test_validate_semantic_rejects_empty_scope(self, adapter, kwargs):
        result = await adapter.validate_semantic(**kwargs)

        assert result.valid is False
        assert result.issues == [
            ValidationIssue(severity="error", message="scope must be one of: all, semantic_model")
        ]

    @pytest.mark.asyncio
    async def test_validate_semantic_returns_errors_from_lint_stage(self, adapter):
        lint_results = _validation_results(errors=["bad lint"], has_blocking_issues=True)

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter, "_collect_model_file_paths", return_value=["/tmp/models/orders.yml"]
            ),
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results

            result = await adapter.validate_semantic()

        assert result.valid is False
        assert result.issues == [ValidationIssue(severity="error", message="bad lint")]

    @pytest.mark.asyncio
    async def test_validate_semantic_returns_errors_from_parsing_stage(self, adapter):
        lint_results = _validation_results()
        parsing_issues = _validation_results(
            errors=["missing primary entity"],
            has_blocking_issues=True,
        )

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter,
                "_collect_model_file_paths",
                return_value=["/tmp/models/orders.yml"],
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model=None),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results

            result = await adapter.validate_semantic()

        assert result.valid is False
        assert result.issues == [
            ValidationIssue(severity="error", message="missing primary entity")
        ]
        mock_validator_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_semantic_classifies_semantic_validation_exception(self, adapter):
        lint_results = _validation_results()
        parsing_issues = _validation_results()

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter,
                "_collect_model_file_paths",
                return_value=["/tmp/models/orders.yml"],
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model="user-model"),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results
            mock_validator_cls.return_value.validate_model.side_effect = RuntimeError(
                "invalid metric graph"
            )

            result = await adapter.validate_semantic()

        assert result.valid is False
        assert result.issues == [
            ValidationIssue(
                severity="error",
                message="Semantic validation failed: invalid metric graph",
            )
        ]

    @pytest.mark.asyncio
    async def test_validate_semantic_classifies_data_warehouse_exception(self, adapter):
        adapter.client = SimpleNamespace(sql_client=MagicMock(), system_schema="datus_system")
        lint_results = _validation_results()
        parsing_issues = _validation_results()
        semantic_issues = _validation_results()

        with (
            patch("metricflow.engine.utils.path_to_models", return_value="/tmp/models"),
            patch("metricflow.model.parsing.config_linter.ConfigLinter") as mock_linter_cls,
            patch.object(
                adapter,
                "_collect_model_file_paths",
                return_value=["/tmp/models/orders.yml"],
            ),
            patch.object(
                adapter,
                "_model_build_result_from_config",
                return_value=SimpleNamespace(issues=parsing_issues, model="user-model"),
            ),
            patch("metricflow.model.model_validator.ModelValidator") as mock_validator_cls,
            patch("metricflow.model.data_warehouse_model_validator.DataWarehouseModelValidator"),
            patch.object(
                adapter,
                "_run_dw_validations",
                side_effect=RuntimeError("warehouse unavailable"),
            ),
        ):
            mock_linter_cls.return_value.lint_files.return_value = lint_results
            mock_validator_cls.return_value.validate_model.return_value = SimpleNamespace(
                issues=semantic_issues
            )

            result = await adapter.validate_semantic()

        assert result.valid is False
        assert result.issues == [
            ValidationIssue(
                severity="error",
                message="Data warehouse validation failed: warehouse unavailable",
            )
        ]

    def test_convert_validation_results_maps_errors_and_warnings(self, adapter):
        results = _validation_results(errors=["bad metric"], warnings=["deprecated field"])

        converted = adapter._convert_validation_results(results)

        assert converted == [
            ValidationIssue(severity="error", message="bad metric"),
            ValidationIssue(severity="warning", message="deprecated field"),
        ]

    def test_run_dw_validations_uses_adapter_timeout(self, adapter):
        adapter.timeout = 42
        dw_validator = MagicMock()

        with patch(
            "metricflow.model.validations.validator_helpers.ModelValidationResults.merge",
            return_value="merged",
        ):
            merged = adapter._run_dw_validations(dw_validator, model="user-model")

        assert merged == "merged"
        dw_validator.validate_data_sources.assert_called_once_with("user-model", 42)
        dw_validator.validate_dimensions.assert_called_once_with("user-model", 42)
        dw_validator.validate_identifiers.assert_called_once_with("user-model", 42)
        dw_validator.validate_measures.assert_called_once_with("user-model", 42)
        dw_validator.validate_metrics.assert_called_once_with("user-model", 42)

    def test_run_dw_validations_can_skip_metrics(self, adapter):
        adapter.timeout = 42
        dw_validator = MagicMock()

        with patch(
            "metricflow.model.validations.validator_helpers.ModelValidationResults.merge",
            return_value="merged",
        ) as mock_merge:
            merged = adapter._run_dw_validations(
                dw_validator, model="user-model", include_metrics=False
            )

        assert merged == "merged"
        dw_validator.validate_data_sources.assert_called_once_with("user-model", 42)
        dw_validator.validate_dimensions.assert_called_once_with("user-model", 42)
        dw_validator.validate_identifiers.assert_called_once_with("user-model", 42)
        dw_validator.validate_measures.assert_called_once_with("user-model", 42)
        dw_validator.validate_metrics.assert_not_called()
        assert len(mock_merge.call_args.args[0]) == 4


class TestConfiguration:
    def test_config_defaults(self):
        config = MetricFlowConfig(datasource="test")

        assert config.datasource == "test"
        assert config.service_type == "metricflow"
        assert config.config_path is None
        assert config.timeout == 300
        assert config.db_config is None
        assert config.agent_home is None

    def test_config_custom_values(self):
        config = MetricFlowConfig(
            datasource="prod",
            config_path="/tmp/agent.yml",
            timeout=600,
            db_config={"type": "postgres", "database": "analytics"},
            agent_home="/tmp/datus-home",
        )

        assert config.datasource == "prod"
        assert config.config_path == "/tmp/agent.yml"
        assert config.timeout == 600
        assert config.db_config == {"type": "postgres", "database": "analytics"}
        assert config.agent_home == "/tmp/datus-home"

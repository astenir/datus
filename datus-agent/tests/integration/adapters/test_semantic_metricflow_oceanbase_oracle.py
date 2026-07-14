"""Read-only MetricFlow nightly tests for an OceanBase Oracle tenant."""

import datetime
import os
import re

import pytest

from tests.nightly_requirements import import_required, require_opt_in_env

require_opt_in_env("ADAPTERS_METRICFLOW_OCEANBASE_ORACLE", "tests/integration/adapters/README.md")

datus_semantic_metricflow = import_required(
    "datus_semantic_metricflow",
    reason="datus-semantic-metricflow is required for the OceanBase Oracle MetricFlow suite",
)
datus_oceanbase_oracle = import_required(
    "datus_oceanbase_oracle",
    reason="datus-oceanbase-oracle is required for the OceanBase Oracle MetricFlow suite",
)

MetricFlowAdapter = datus_semantic_metricflow.MetricFlowAdapter
MetricFlowConfig = datus_semantic_metricflow.MetricFlowConfig
OceanBaseOracleConfig = datus_oceanbase_oracle.OceanBaseOracleConfig
OceanBaseOracleConnector = datus_oceanbase_oracle.OceanBaseOracleConnector

pytestmark = [pytest.mark.integration, pytest.mark.nightly, pytest.mark.asyncio]

_ORACLE_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_$#]*")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for the read-only OceanBase Oracle MetricFlow suite")
    return value


def _identifier_env(name: str, default: str | None = None) -> str:
    value = (os.getenv(name, default or "") or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for the read-only OceanBase Oracle MetricFlow suite")
    if not _ORACLE_IDENTIFIER.fullmatch(value):
        raise RuntimeError(f"{name} must be a standard unquoted Oracle identifier, got {value!r}")
    return value.upper()


def _date_env(name: str) -> str:
    value = _required_env(name)
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{name} must use YYYY-MM-DD format, got {value!r}") from exc


_HOST = os.environ["OCEANBASE_ORACLE_HOST"]
_PORT = int(os.getenv("OCEANBASE_ORACLE_PORT", "2883"))
_USERNAME = os.environ["OCEANBASE_ORACLE_USERNAME"]
_PASSWORD = os.getenv("OCEANBASE_ORACLE_PASSWORD", "")
_DATABASE = os.getenv("OCEANBASE_ORACLE_DATABASE", "")
_SCHEMA = _identifier_env("OCEANBASE_ORACLE_SCHEMA")
_JAR_PATH = os.environ["OCEANBASE_ORACLE_JAR_PATH"]

_RELATION = _identifier_env("OCEANBASE_ORACLE_METRICFLOW_RELATION")
_ID_COLUMN = _identifier_env("OCEANBASE_ORACLE_METRICFLOW_ID_COLUMN", "ID")
_AMOUNT_COLUMN = _identifier_env("OCEANBASE_ORACLE_METRICFLOW_AMOUNT_COLUMN", "AMOUNT")
_TIME_COLUMN = _identifier_env("OCEANBASE_ORACLE_METRICFLOW_TIME_COLUMN", "CREATED_AT")
_TIME_START = _date_env("OCEANBASE_ORACLE_METRICFLOW_TIME_START")
_TIME_END = _date_env("OCEANBASE_ORACLE_METRICFLOW_TIME_END")

if _TIME_START > _TIME_END:
    raise RuntimeError("OCEANBASE_ORACLE_METRICFLOW_TIME_START must not be after TIME_END")

_QUALIFIED_RELATION = f'"{_SCHEMA}"."{_RELATION}"'

_SEMANTIC_YAML = f"""\
data_source:
  name: mf_orders
  sql_table: {_SCHEMA}.{_RELATION}
  identifiers:
    - name: order_id
      type: primary
      expr: {_ID_COLUMN}
  measures:
    - name: total_amount
      agg: sum
      expr: {_AMOUNT_COLUMN}
    - name: order_count
      agg: count
      expr: {_ID_COLUMN}
  dimensions:
    - name: created_at
      type: time
      expr: {_TIME_COLUMN}
      type_params:
        is_primary: true
        time_granularity: day
---
metric:
  name: total_amount
  type: measure_proxy
  type_params:
    measure: total_amount
---
metric:
  name: order_count
  type: measure_proxy
  type_params:
    measure: order_count
---
metric:
  name: average_order_amount
  type: ratio
  type_params:
    numerator: total_amount
    denominator: order_count
"""

_BASELINE_SQL = f"""\
SELECT
    SUM("{_AMOUNT_COLUMN}") AS "TOTAL_AMOUNT",
    COUNT("{_ID_COLUMN}") AS "ORDER_COUNT"
FROM {_QUALIFIED_RELATION}
WHERE "{_TIME_COLUMN}" >= TO_DATE(?, 'YYYY-MM-DD')
  AND "{_TIME_COLUMN}" <= TO_DATE(?, 'YYYY-MM-DD')
"""


def _connector_config() -> dict:
    return {
        "host": _HOST,
        "port": _PORT,
        "username": _USERNAME,
        "password": _PASSWORD,
        "database": _DATABASE,
        "schema": _SCHEMA,
        "jar_path": _JAR_PATH,
        "connect_timeout_seconds": 30,
        "query_timeout_seconds": 60,
    }


def _metricflow_db_config() -> dict[str, str]:
    return {
        "type": "oceanbase-oracle",
        **{key: str(value) for key, value in _connector_config().items()},
    }


def _read_baseline(connector) -> tuple[float, int]:
    result = connector.query_dataframe(_BASELINE_SQL, (_TIME_START, _TIME_END))
    if len(result.index) != 1:
        raise AssertionError(f"Expected one baseline row from {_QUALIFIED_RELATION}, got {len(result.index)}")

    total_amount = result.iloc[0]["TOTAL_AMOUNT"]
    order_count = int(result.iloc[0]["ORDER_COUNT"])
    if order_count <= 0 or total_amount is None:
        raise AssertionError(
            f"Read-only acceptance relation {_QUALIFIED_RELATION} has no usable rows between "
            f"{_TIME_START} and {_TIME_END}"
        )
    return float(total_amount), order_count


@pytest.fixture(scope="module")
def mf_config(tmp_path_factory):
    yaml_dir = tmp_path_factory.mktemp("mf_oceanbase_oracle_models")
    (yaml_dir / "mf_orders.yaml").write_text(_SEMANTIC_YAML)
    return MetricFlowConfig(
        datasource="mf_oceanbase_oracle_nightly",
        db_config=_metricflow_db_config(),
        semantic_models_path=str(yaml_dir),
    )


@pytest.fixture(scope="module")
def readonly_baseline():
    connector = OceanBaseOracleConnector(_connector_config())
    before = _read_baseline(connector)
    try:
        yield before
        after = _read_baseline(connector)
        assert after[0] == pytest.approx(before[0]), "Acceptance data changed while the nightly was running"
        assert after[1] == before[1], "Acceptance row count changed while the nightly was running"
    finally:
        connector.close()


@pytest.fixture(scope="module")
def mf_adapter(mf_config):
    adapter = MetricFlowAdapter(mf_config)
    yield adapter
    adapter.client.sql_client.close()


async def test_readonly_configs_match_consumers():
    connector_config = OceanBaseOracleConfig(**_connector_config())
    metricflow_config = MetricFlowConfig(
        datasource="mf_oceanbase_oracle_nightly",
        db_config=_metricflow_db_config(),
    )

    assert connector_config.port == _PORT
    assert connector_config.schema_name == _SCHEMA
    assert metricflow_config.db_config is not None
    assert all(isinstance(value, str) for value in metricflow_config.db_config.values())


async def test_validate_semantic_passes(mf_adapter):
    result = await mf_adapter.validate_semantic()
    errors = [issue for issue in result.issues if issue.severity == "error"]
    assert result.valid, f"Unexpected validation errors: {errors}"


async def test_query_metrics_dry_run_returns_oracle_sql(mf_adapter):
    result = await mf_adapter.query_metrics(
        ["total_amount"],
        time_start=_TIME_START,
        time_end=_TIME_END,
        limit=2,
        dry_run=True,
    )
    sql = result.metadata.get("sql", "")
    assert sql
    assert "LIMIT" not in sql.upper()
    assert "FETCH FIRST 2 ROWS ONLY" in sql.upper()


async def test_query_metrics_live_matches_read_only_baseline(mf_adapter, readonly_baseline):
    expected_total, expected_count = readonly_baseline
    result = await mf_adapter.query_metrics(
        ["total_amount", "order_count"],
        time_start=_TIME_START,
        time_end=_TIME_END,
    )
    assert len(result.data) == 1
    assert float(result.data[0]["total_amount"]) == pytest.approx(expected_total)
    assert int(result.data[0]["order_count"]) == expected_count


async def test_query_ratio_metric_live(mf_adapter, readonly_baseline):
    expected_total, expected_count = readonly_baseline
    result = await mf_adapter.query_metrics(
        ["average_order_amount"],
        time_start=_TIME_START,
        time_end=_TIME_END,
    )
    assert len(result.data) == 1
    assert float(result.data[0]["average_order_amount"]) == pytest.approx(expected_total / expected_count)


@pytest.mark.parametrize("granularity", ["day", "week", "month", "quarter", "year"])
async def test_query_metrics_with_declared_time_granularities(mf_adapter, readonly_baseline, granularity):
    expected_total, _ = readonly_baseline
    result = await mf_adapter.query_metrics(
        ["total_amount"],
        dimensions=["created_at"],
        time_start=_TIME_START,
        time_end=_TIME_END,
        time_granularity=granularity,
        order_by=["metric_time"],
    )
    assert result.data
    total = sum(float(row["total_amount"]) for row in result.data if row.get("total_amount") is not None)
    assert total == pytest.approx(expected_total)

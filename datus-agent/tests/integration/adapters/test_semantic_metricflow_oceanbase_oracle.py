"""MetricFlow semantic adapter nightly tests for an OceanBase Oracle tenant."""

import logging
import os

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
OceanBaseOracleConnector = datus_oceanbase_oracle.OceanBaseOracleConnector

logger = logging.getLogger(__name__)
pytestmark = [pytest.mark.integration, pytest.mark.nightly, pytest.mark.asyncio]

_HOST = os.environ["OCEANBASE_ORACLE_HOST"]
_PORT = int(os.getenv("OCEANBASE_ORACLE_PORT", "2883"))
_USERNAME = os.environ["OCEANBASE_ORACLE_USERNAME"]
_PASSWORD = os.getenv("OCEANBASE_ORACLE_PASSWORD", "")
_DATABASE = os.getenv("OCEANBASE_ORACLE_DATABASE", "")
_SCHEMA = os.environ["OCEANBASE_ORACLE_SCHEMA"].upper()
_JAR_PATH = os.environ["OCEANBASE_ORACLE_JAR_PATH"]

_DATA_TABLE = "MF_ORDERS"
_TIME_SPINE_TABLE = "MF_TIME_SPINE"

_SEMANTIC_YAML = f"""\
data_source:
  name: mf_orders
  sql_table: {_SCHEMA}.{_DATA_TABLE}
  identifiers:
    - name: order_id
      type: primary
      expr: id
  measures:
    - name: total_amount
      agg: sum
      expr: amount
    - name: order_count
      agg: count
      expr: id
  dimensions:
    - name: created_at
      type: time
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


def _db_config() -> dict:
    return {
        "type": "oceanbase-oracle",
        "host": _HOST,
        "port": str(_PORT),
        "username": _USERNAME,
        "password": _PASSWORD,
        "database": _DATABASE,
        "schema": _SCHEMA,
        "jar_path": _JAR_PATH,
        "connect_timeout_seconds": "30",
        "query_timeout_seconds": "60",
    }


def _drop_table(connector, table_name: str) -> None:
    try:
        connector.execute_statement(f'DROP TABLE "{_SCHEMA}"."{table_name}" PURGE')
    except Exception:
        logger.debug("Ignoring missing OceanBase Oracle test table %s", table_name, exc_info=True)


@pytest.fixture(scope="module")
def mf_config(tmp_path_factory):
    yaml_dir = tmp_path_factory.mktemp("mf_oceanbase_oracle_models")
    (yaml_dir / "mf_orders.yaml").write_text(_SEMANTIC_YAML)
    return MetricFlowConfig(
        datasource="mf_oceanbase_oracle_nightly",
        db_config=_db_config(),
        semantic_models_path=str(yaml_dir),
    )


@pytest.fixture(scope="module")
def seeded_db():
    connector = OceanBaseOracleConnector(_db_config())
    _drop_table(connector, _TIME_SPINE_TABLE)
    _drop_table(connector, _DATA_TABLE)
    connector.execute_statement(
        f'CREATE TABLE "{_SCHEMA}"."{_DATA_TABLE}" '
        '("ID" NUMBER(10) PRIMARY KEY, "AMOUNT" NUMBER(10,2), "CREATED_AT" DATE)'
    )
    connector.execute_statement(f'CREATE TABLE "{_SCHEMA}"."{_TIME_SPINE_TABLE}" ("DS" DATE NOT NULL)')
    for row_id, amount, created_at in [
        (1, 10.0, "2020-01-01"),
        (2, 20.0, "2020-01-02"),
        (3, 30.0, "2020-01-03"),
        (4, 40.0, "2020-01-04"),
        (5, 50.0, "2020-01-05"),
    ]:
        connector.execute_statement(
            f'INSERT INTO "{_SCHEMA}"."{_DATA_TABLE}" ("ID", "AMOUNT", "CREATED_AT") '
            "VALUES (?, ?, TO_DATE(?, 'YYYY-MM-DD'))",
            (row_id, amount, created_at),
        )
    for day in range(1, 11):
        connector.execute_statement(
            f'INSERT INTO "{_SCHEMA}"."{_TIME_SPINE_TABLE}" ("DS") VALUES (TO_DATE(?, \'YYYY-MM-DD\'))',
            (f"2020-01-{day:02d}",),
        )

    yield

    _drop_table(connector, _TIME_SPINE_TABLE)
    _drop_table(connector, _DATA_TABLE)
    connector.close()


@pytest.fixture(scope="module")
def mf_adapter(mf_config, seeded_db):
    adapter = MetricFlowAdapter(mf_config)
    yield adapter
    adapter.client.sql_client.close()


async def test_validate_semantic_passes(mf_adapter):
    result = await mf_adapter.validate_semantic()
    errors = [issue for issue in result.issues if issue.severity == "error"]
    assert result.valid, f"Unexpected validation errors: {errors}"


async def test_query_metrics_dry_run_returns_oracle_sql(mf_adapter):
    result = await mf_adapter.query_metrics(["total_amount"], limit=2, dry_run=True)
    sql = result.metadata.get("sql", "")
    assert sql
    assert "LIMIT" not in sql.upper()
    assert "FETCH FIRST 2 ROWS ONLY" in sql.upper()


async def test_query_metrics_live(mf_adapter):
    result = await mf_adapter.query_metrics(["total_amount", "order_count"])
    assert len(result.data) == 1
    assert float(result.data[0]["total_amount"]) == pytest.approx(150.0)
    assert int(result.data[0]["order_count"]) == 5


async def test_query_ratio_metric_live(mf_adapter):
    result = await mf_adapter.query_metrics(["average_order_amount"])
    assert len(result.data) == 1
    assert float(result.data[0]["average_order_amount"]) == pytest.approx(30.0)


async def test_query_metrics_with_time_filter(mf_adapter):
    result = await mf_adapter.query_metrics(
        ["total_amount"],
        time_start="2020-01-01",
        time_end="2020-01-03",
    )
    total = sum(float(row["total_amount"]) for row in result.data if row.get("total_amount") is not None)
    assert total == pytest.approx(60.0)


@pytest.mark.parametrize("granularity", ["day", "week", "month", "quarter", "year"])
async def test_query_metrics_with_declared_time_granularities(mf_adapter, granularity):
    result = await mf_adapter.query_metrics(
        ["total_amount"],
        dimensions=["created_at"],
        time_granularity=granularity,
        order_by=["metric_time"],
    )
    assert result.data
    total = sum(float(row["total_amount"]) for row in result.data if row.get("total_amount") is not None)
    assert total == pytest.approx(150.0)

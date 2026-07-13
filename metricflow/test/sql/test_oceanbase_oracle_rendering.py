"""Unit tests for OceanBase Oracle SQL rendering."""

import pytest

from metricflow.dataflow.sql_table import SqlTable
from metricflow.sql.render.oceanbase_oracle import (
    OceanBaseOracleSqlExpressionRenderer,
    OceanBaseOracleSqlQueryPlanRenderer,
)
from metricflow.sql.sql_exprs import (
    SqlAggregateFunctionExpression,
    SqlColumnReference,
    SqlColumnReferenceExpression,
    SqlDateTruncExpression,
    SqlFunction,
    SqlRatioComputationExpression,
    SqlStringExpression,
    SqlTimeDeltaExpression,
)
from metricflow.sql.sql_plan import SqlQueryPlan, SqlSelectColumn, SqlSelectStatementNode, SqlTableFromClauseNode
from metricflow.time.time_granularity import TimeGranularity


@pytest.fixture
def renderer() -> OceanBaseOracleSqlExpressionRenderer:
    return OceanBaseOracleSqlExpressionRenderer()


@pytest.mark.parametrize(
    ("granularity", "expected"),
    [
        (TimeGranularity.DAY, "TRUNC(a.ds, 'DD')"),
        (TimeGranularity.WEEK, "TRUNC(a.ds, 'IW')"),
        (TimeGranularity.MONTH, "TRUNC(a.ds, 'MM')"),
        (TimeGranularity.QUARTER, "TRUNC(a.ds, 'Q')"),
        (TimeGranularity.YEAR, "TRUNC(a.ds, 'YYYY')"),
    ],
)
def test_date_trunc_uses_oracle_formats(
    renderer: OceanBaseOracleSqlExpressionRenderer,
    granularity: TimeGranularity,
    expected: str,
) -> None:
    result = renderer.visit_date_trunc_expr(
        SqlDateTruncExpression(
            time_granularity=granularity,
            arg=SqlColumnReferenceExpression(SqlColumnReference("a", "ds")),
        )
    )

    assert result.sql == expected


@pytest.mark.parametrize(
    ("granularity", "count", "expected"),
    [
        (TimeGranularity.DAY, 2, "a.ds - NUMTODSINTERVAL(2, 'DAY')"),
        (TimeGranularity.WEEK, 2, "a.ds - NUMTODSINTERVAL(14, 'DAY')"),
        (TimeGranularity.MONTH, 2, "ADD_MONTHS(a.ds, -2)"),
        (TimeGranularity.QUARTER, 2, "ADD_MONTHS(a.ds, -6)"),
        (TimeGranularity.YEAR, 2, "ADD_MONTHS(a.ds, -24)"),
    ],
)
def test_time_delta_uses_oracle_interval_functions(
    renderer: OceanBaseOracleSqlExpressionRenderer,
    granularity: TimeGranularity,
    count: int,
    expected: str,
) -> None:
    result = renderer.visit_time_delta_expr(
        SqlTimeDeltaExpression(
            arg=SqlColumnReferenceExpression(SqlColumnReference("a", "ds")),
            count=count,
            granularity=granularity,
            grain_to_date=False,
        )
    )

    assert result.sql == expected


def test_grain_to_date_reuses_oracle_trunc(renderer: OceanBaseOracleSqlExpressionRenderer) -> None:
    result = renderer.visit_time_delta_expr(
        SqlTimeDeltaExpression(
            arg=SqlColumnReferenceExpression(SqlColumnReference("a", "ds")),
            count=1,
            granularity=TimeGranularity.MONTH,
            grain_to_date=True,
        )
    )

    assert result.sql == "TRUNC(a.ds, 'MM')"


def test_ratio_uses_oracle_binary_double(renderer: OceanBaseOracleSqlExpressionRenderer) -> None:
    result = renderer.render_sql_expr(
        SqlRatioComputationExpression(
            numerator=SqlAggregateFunctionExpression(
                SqlFunction.SUM,
                sql_function_args=[SqlStringExpression(sql_expr="amount", requires_parenthesis=False)],
            ),
            denominator=SqlColumnReferenceExpression(SqlColumnReference(column_name="order_count", table_alias="a")),
        )
    )

    assert result.sql == (
        "CAST(SUM(amount) AS BINARY_DOUBLE) / "
        "CAST(NULLIF(a.order_count, 0) AS BINARY_DOUBLE)"
    )


def test_query_limit_uses_fetch_first() -> None:
    select_node = SqlSelectStatementNode(
        description="OceanBase Oracle limit",
        select_columns=(SqlSelectColumn(expr=SqlStringExpression("1"), column_alias="value"),),
        from_source=SqlTableFromClauseNode(SqlTable(schema_name="APP", table_name="ORDERS")),
        from_source_alias="a",
        joins_descs=(),
        group_bys=(),
        order_bys=(),
        limit=10,
    )

    result = OceanBaseOracleSqlQueryPlanRenderer().render_sql_query_plan(
        SqlQueryPlan(plan_id="oracle-limit", render_node=select_node)
    )

    assert "LIMIT" not in result.sql
    assert result.sql.endswith("FETCH FIRST 10 ROWS ONLY")

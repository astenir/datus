"""OceanBase Oracle SQL expression and query-plan rendering."""

from metricflow.sql.render.expr_renderer import (
    DefaultSqlExpressionRenderer,
    SqlExpressionRenderer,
    SqlExpressionRenderResult,
)
from metricflow.sql.render.sql_plan_renderer import (
    DefaultSqlQueryPlanRenderer,
    SqlPlanRenderResult,
)
from metricflow.sql.sql_exprs import (
    SqlCastToTimestampExpression,
    SqlDateTruncExpression,
    SqlStringLiteralExpression,
    SqlTimeDeltaExpression,
)
from metricflow.sql.sql_plan import SqlSelectStatementNode
from metricflow.time.time_granularity import TimeGranularity

_TRUNC_FORMAT = {
    TimeGranularity.DAY: "DD",
    TimeGranularity.WEEK: "IW",
    TimeGranularity.MONTH: "MM",
    TimeGranularity.QUARTER: "Q",
    TimeGranularity.YEAR: "YYYY",
}


class OceanBaseOracleSqlExpressionRenderer(DefaultSqlExpressionRenderer):
    """Render expressions using the OceanBase Oracle compatibility dialect."""

    @property
    def double_data_type(self) -> str:
        return "BINARY_DOUBLE"

    def visit_cast_to_timestamp_expr(self, node: SqlCastToTimestampExpression) -> SqlExpressionRenderResult:
        if not isinstance(node.arg, SqlStringLiteralExpression):
            return super().visit_cast_to_timestamp_expr(node)

        argument = self.render_sql_expr(node.arg)
        return SqlExpressionRenderResult(
            sql=f"TO_TIMESTAMP({argument.sql}, 'YYYY-MM-DD')",
            execution_parameters=argument.execution_parameters,
        )

    @staticmethod
    def _date_trunc_sql(argument: str, granularity: TimeGranularity) -> str:
        return f"TRUNC({argument}, '{_TRUNC_FORMAT[granularity]}')"

    def visit_date_trunc_expr(self, node: SqlDateTruncExpression) -> SqlExpressionRenderResult:
        argument = self.render_sql_expr(node.arg)
        return SqlExpressionRenderResult(
            sql=self._date_trunc_sql(argument.sql, node.time_granularity),
            execution_parameters=argument.execution_parameters,
        )

    def visit_time_delta_expr(self, node: SqlTimeDeltaExpression) -> SqlExpressionRenderResult:
        argument = node.arg.accept(self)
        if node.grain_to_date:
            sql = self._date_trunc_sql(argument.sql, node.granularity)
        elif node.granularity is TimeGranularity.DAY:
            sql = f"{argument.sql} - NUMTODSINTERVAL({node.count}, 'DAY')"
        elif node.granularity is TimeGranularity.WEEK:
            sql = f"{argument.sql} - NUMTODSINTERVAL({node.count * 7}, 'DAY')"
        else:
            month_count = {
                TimeGranularity.MONTH: node.count,
                TimeGranularity.QUARTER: node.count * 3,
                TimeGranularity.YEAR: node.count * 12,
            }[node.granularity]
            sql = f"ADD_MONTHS({argument.sql}, -{month_count})"
        return SqlExpressionRenderResult(sql=sql, execution_parameters=argument.execution_parameters)


class OceanBaseOracleSqlQueryPlanRenderer(DefaultSqlQueryPlanRenderer):
    """Render query plans with Oracle-style row limiting."""

    EXPR_RENDERER = OceanBaseOracleSqlExpressionRenderer()

    def visit_select_statement_node(self, node: SqlSelectStatementNode) -> SqlPlanRenderResult:
        result = super().visit_select_statement_node(node)
        if node.limit is None:
            return result

        limit_suffix = f"\nLIMIT {node.limit}"
        if not result.sql.endswith(limit_suffix):
            raise RuntimeError("Expected the default renderer to place LIMIT at the end of the query")
        return SqlPlanRenderResult(
            sql=f"{result.sql[: -len(limit_suffix)]}\nFETCH FIRST {node.limit} ROWS ONLY",
            execution_parameters=result.execution_parameters,
        )

    @property
    def expr_renderer(self) -> SqlExpressionRenderer:
        return self.EXPR_RENDERER

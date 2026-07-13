from metricflow.object_utils import assert_values_exhausted
from metricflow.sql.render.expr_renderer import (
    DefaultSqlExpressionRenderer,
    SqlExpressionRenderer,
    SqlExpressionRenderResult,
)
from metricflow.sql.render.sql_plan_renderer import DefaultSqlQueryPlanRenderer, SqlPlanRenderResult
from metricflow.sql.sql_bind_parameters import SqlBindParameters
from metricflow.sql.sql_plan import SqlSelectColumn
from typing import Sequence, Tuple
from metricflow.sql.sql_exprs import (
    SqlColumnAliasReferenceExpression,
    SqlColumnReferenceExpression,
    SqlDateTruncExpression,
    SqlGenerateUuidExpression,
    SqlPercentileExpression,
    SqlPercentileFunctionType,
    SqlStringExpression,
    SqlTimeDeltaExpression,
)
from metricflow.sql.sql_plan import SqlTableFromClauseNode
from metricflow.time.time_granularity import TimeGranularity


class SqliteSqlExpressionRenderer(DefaultSqlExpressionRenderer):
    """Expression renderer for the SQLite engine."""

    @staticmethod
    def _quote_identifier_if_needed(identifier: str) -> str:
        """Quote identifier with double quotes if it's a SQLite reserved keyword or contains special chars."""
        # Common SQLite reserved keywords that might be used as column names
        reserved_keywords = {
            "transaction",
            "order",
            "group",
            "user",
            "table",
            "column",
            "index",
            "view",
            "trigger",
            "schema",
            "database",
            "select",
            "insert",
            "update",
            "delete",
            "from",
            "where",
            "join",
            "inner",
            "outer",
            "left",
            "right",
            "on",
            "as",
            "and",
            "or",
            "not",
            "in",
            "like",
            "between",
            "case",
            "when",
            "then",
            "else",
            "end",
            "is",
            "null",
            "primary",
            "key",
            "foreign",
            "references",
            "unique",
            "check",
            "default",
            "create",
            "alter",
            "drop",
            "exists",
            "if",
            "distinct",
            "union",
            "all",
            "intersect",
            "except",
            "order",
            "by",
            "limit",
            "offset",
            "having",
            "with",
            "recursive",
            "window",
            "over",
            "partition",
        }

        # Quote if it's a reserved keyword (case insensitive) or contains special characters
        if (
            identifier.lower() in reserved_keywords
            or not identifier.replace("_", "")
            .replace("$", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .replace("-", "")
            .isalnum()
            or identifier[0].isdigit()
            or " " in identifier
            or "(" in identifier
            or ")" in identifier
        ):
            return f'"{identifier}"'
        return identifier

    def visit_date_trunc_expr(self, node: SqlDateTruncExpression) -> SqlExpressionRenderResult:  # noqa: D
        arg_rendered = self.render_sql_expr(node.arg)

        # SQLite doesn't have DATE_TRUNC, so we implement it using date functions
        if node.time_granularity == TimeGranularity.DAY:
            sql = f"DATE({arg_rendered.sql})"
        elif node.time_granularity == TimeGranularity.WEEK:
            # Get Monday of the week containing the date
            sql = f"DATE({arg_rendered.sql}, 'weekday 1', '-6 days')"
        elif node.time_granularity == TimeGranularity.MONTH:
            sql = f"DATE({arg_rendered.sql}, 'start of month')"
        elif node.time_granularity == TimeGranularity.QUARTER:
            # SQLite doesn't have quarter function, approximate with month
            sql = f"DATE({arg_rendered.sql}, 'start of month', '-' || ((CAST(strftime('%m', {arg_rendered.sql}) AS INTEGER) - 1) % 3) || ' months')"
        elif node.time_granularity == TimeGranularity.YEAR:
            sql = f"DATE({arg_rendered.sql}, 'start of year')"
        else:
            # Default to day truncation
            sql = f"DATE({arg_rendered.sql})"

        return SqlExpressionRenderResult(
            sql=sql,
            execution_parameters=arg_rendered.execution_parameters,
        )

    def visit_time_delta_expr(self, node: SqlTimeDeltaExpression) -> SqlExpressionRenderResult:  # noqa: D
        arg_rendered = node.arg.accept(self)
        if node.grain_to_date:
            # Use the same logic as visit_date_trunc_expr for consistency
            if node.granularity == TimeGranularity.DAY:
                sql = f"DATE({arg_rendered.sql})"
            elif node.granularity == TimeGranularity.WEEK:
                sql = f"DATE({arg_rendered.sql}, 'weekday 1', '-6 days')"
            elif node.granularity == TimeGranularity.MONTH:
                sql = f"DATE({arg_rendered.sql}, 'start of month')"
            elif node.granularity == TimeGranularity.QUARTER:
                sql = f"DATE({arg_rendered.sql}, 'start of month', '-' || ((CAST(strftime('%m', {arg_rendered.sql}) AS INTEGER) - 1) % 3) || ' months')"
            elif node.granularity == TimeGranularity.YEAR:
                sql = f"DATE({arg_rendered.sql}, 'start of year')"
            else:
                sql = f"DATE({arg_rendered.sql})"

            return SqlExpressionRenderResult(
                sql=sql,
                execution_parameters=arg_rendered.execution_parameters,
            )

        count = node.count
        granularity = node.granularity
        if granularity == TimeGranularity.QUARTER:
            granularity = TimeGranularity.MONTH
            count *= 3

        # SQLite uses different syntax for date arithmetic
        if granularity == TimeGranularity.DAY:
            return SqlExpressionRenderResult(
                sql=f"DATE({arg_rendered.sql}, '{count} days')",
                execution_parameters=arg_rendered.execution_parameters,
            )
        elif granularity == TimeGranularity.MONTH:
            return SqlExpressionRenderResult(
                sql=f"DATE({arg_rendered.sql}, '{count} months')",
                execution_parameters=arg_rendered.execution_parameters,
            )
        elif granularity == TimeGranularity.YEAR:
            return SqlExpressionRenderResult(
                sql=f"DATE({arg_rendered.sql}, '{count} years')",
                execution_parameters=arg_rendered.execution_parameters,
            )
        else:
            # For other granularities, we'll use seconds-based calculation
            seconds = {
                TimeGranularity.SECOND: 1,
                TimeGranularity.MINUTE: 60,
                TimeGranularity.HOUR: 3600,
            }[granularity] * count
            return SqlExpressionRenderResult(
                sql=f"DATETIME({arg_rendered.sql}, '{seconds} seconds')",
                execution_parameters=arg_rendered.execution_parameters,
            )

    def visit_generate_uuid_expr(self, node: SqlGenerateUuidExpression) -> SqlExpressionRenderResult:  # noqa: D
        # SQLite doesn't have a built-in UUID function, using random instead
        return SqlExpressionRenderResult(
            sql="RANDOM()",
            execution_parameters=SqlBindParameters(),
        )

    def visit_percentile_expr(self, node: SqlPercentileExpression) -> SqlExpressionRenderResult:
        """Render a percentile expression for SQLite."""
        arg_rendered = self.render_sql_expr(node.order_by_arg)
        params = arg_rendered.execution_parameters
        percentile = node.percentile_args.percentile

        if node.percentile_args.function_type is SqlPercentileFunctionType.CONTINUOUS:
            # SQLite doesn't have native percentile functions, using a simple approximation
            return SqlExpressionRenderResult(
                sql=f"(SELECT {arg_rendered.sql} FROM (SELECT {arg_rendered.sql} ORDER BY {arg_rendered.sql} LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * {percentile} AS INTEGER) FROM (SELECT DISTINCT {arg_rendered.sql}))))",
                execution_parameters=params,
            )
        elif node.percentile_args.function_type is SqlPercentileFunctionType.DISCRETE:
            # SQLite doesn't have native percentile functions, using a simple approximation
            return SqlExpressionRenderResult(
                sql=f"(SELECT {arg_rendered.sql} FROM (SELECT {arg_rendered.sql} ORDER BY {arg_rendered.sql} LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * {percentile} AS INTEGER) FROM (SELECT DISTINCT {arg_rendered.sql}))))",
                execution_parameters=params,
            )
        elif node.percentile_args.function_type is SqlPercentileFunctionType.APPROXIMATE_CONTINUOUS:
            return SqlExpressionRenderResult(
                sql=f"(SELECT {arg_rendered.sql} FROM (SELECT {arg_rendered.sql} ORDER BY {arg_rendered.sql} LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * {percentile} AS INTEGER) FROM (SELECT DISTINCT {arg_rendered.sql}))))",
                execution_parameters=params,
            )
        elif node.percentile_args.function_type is SqlPercentileFunctionType.APPROXIMATE_DISCRETE:
            return SqlExpressionRenderResult(
                sql=f"(SELECT {arg_rendered.sql} FROM (SELECT {arg_rendered.sql} ORDER BY {arg_rendered.sql} LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * {percentile} AS INTEGER) FROM (SELECT DISTINCT {arg_rendered.sql}))))",
                execution_parameters=params,
            )
        else:
            assert_values_exhausted(node.percentile_args.function_type)

    def visit_column_reference_expr(self, node: SqlColumnReferenceExpression) -> SqlExpressionRenderResult:
        """Render a reference to a column in a table with proper quoting for SQLite."""
        quoted_column = self._quote_identifier_if_needed(node.col_ref.column_name)
        return SqlExpressionRenderResult(
            sql=(f"{node.col_ref.table_alias}.{quoted_column}" if node.should_render_table_alias else quoted_column),
            execution_parameters=SqlBindParameters(),
        )

    def visit_column_alias_reference_expr(self, node: SqlColumnAliasReferenceExpression) -> SqlExpressionRenderResult:
        """Render a reference to a column without a known table alias with proper quoting for SQLite."""
        quoted_column = self._quote_identifier_if_needed(node.column_alias)
        return SqlExpressionRenderResult(
            sql=quoted_column,
            execution_parameters=SqlBindParameters(),
        )

    def visit_string_expr(self, node: SqlStringExpression) -> SqlExpressionRenderResult:
        """Render a string expression, quoting if it looks like a column name for SQLite."""
        # Simply quote using the same logic as other identifiers
        sql_expr = self._quote_identifier_if_needed(node.sql_expr)
        return SqlExpressionRenderResult(sql=sql_expr, execution_parameters=node.execution_parameters)


class SqliteSqlQueryPlanRenderer(DefaultSqlQueryPlanRenderer):
    """Plan renderer for the SQLite engine."""

    EXPR_RENDERER = SqliteSqlExpressionRenderer()

    @property
    def expr_renderer(self) -> SqlExpressionRenderer:  # noqa :D
        return self.EXPR_RENDERER

    def visit_table_from_clause_node(self, node: SqlTableFromClauseNode) -> SqlPlanRenderResult:  # noqa: D
        # For SQLite, only use the table name without schema prefix
        return SqlPlanRenderResult(
            sql=node.sql_table.table_name,
            execution_parameters=SqlBindParameters(),
        )

    def _render_select_columns_section(
        self,
        select_columns: Sequence[SqlSelectColumn],
        num_parents: int,
    ) -> Tuple[str, SqlBindParameters]:
        """Override to add proper identifier quoting for SQLite."""
        params = SqlBindParameters()
        select_section_lines = ["SELECT"]
        first_column = True
        for select_column in select_columns:
            expr_rendered = self.EXPR_RENDERER.render_sql_expr(select_column.expr)
            params = params.combine(expr_rendered.execution_parameters)

            # Quote the column alias to handle reserved keywords
            quoted_alias = self.EXPR_RENDERER._quote_identifier_if_needed(select_column.column_alias)
            column_select_str = f"{expr_rendered.sql} AS {quoted_alias}"

            # For cases where the alias is the same as column, just render the expression
            # but still need to check for quoting needs
            if num_parents <= 1 and select_column.expr.as_column_reference_expression:
                column_reference = select_column.expr.as_column_reference_expression.col_ref
                if column_reference.column_name == select_column.column_alias:
                    column_select_str = expr_rendered.sql

            if first_column:
                select_section_lines.append(f"{self.INDENT}{column_select_str}")
                first_column = False
            else:
                select_section_lines.append(f"{self.INDENT}, {column_select_str}")

        return "\n".join(select_section_lines), params

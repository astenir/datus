# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus OSI Compiler: OSI authoring -> Datus Semantic IR.

The compiler parses metric expressions with sqlglot and infers a safe IR. It
only infers in unambiguous cases; anything ambiguous raises an
:class:`OSIValidationError` asking the author for business-semantic hints.

It never connects to a warehouse, executes SQL, or emits backend syntax.
"""

from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import expressions as exp

from datus_semantic_osi.dialects import DEFAULT_SQLGLOT_DIALECT
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import (
    Aggregation,
    DatasetIR,
    FieldIR,
    IdentifierIR,
    MeasureIR,
    MetricInputIR,
    MetricIR,
    MetricKind,
    NonAdditiveDimensionIR,
    PeriodOverPeriodIR,
    RelationshipIR,
    SemanticModelIR,
)
from datus_semantic_osi.profile import (
    OSIDataset,
    OSIDocument,
    OSIMetric,
    OSIMetricInput,
)

_RESERVED_METRIC_METADATA_KEYS = {
    "name",
    "kind",
    "metric_kind",
    "metric_type",
    "description",
    "dataset",
    "datasets",
    "measures",
    "measure",
    "inputs",
    "expression",
    "expr",
    "numerator",
    "denominator",
    "time_dimension",
    "window",
    "grain_to_date",
    "offset_window",
    "period_over_period",
    "format",
    "unit",
}

# sqlglot aggregate node -> our Aggregation
_AGG_NODES = {
    exp.Sum: Aggregation.SUM,
    exp.Avg: Aggregation.AVERAGE,
    exp.Min: Aggregation.MIN,
    exp.Max: Aggregation.MAX,
}


def _sanitize(name: str) -> str:
    """Turn a column expression into a safe measure-name fragment."""
    # use the trailing identifier of a qualified column (orders.amount -> amount)
    name = name.split(".")[-1]
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def _measure_from_aggregate(node: exp.Expression, *, dialect: str) -> MeasureIR:
    """Map a single sqlglot aggregate node to a backing MeasureIR."""
    if isinstance(node, exp.Count):
        arg = node.this
        if isinstance(arg, exp.Star) or arg is None:
            return MeasureIR(name="rows_count", agg=Aggregation.COUNT, expr="1")
        if isinstance(arg, exp.Distinct):
            cols = arg.expressions or ([arg.this] if arg.this else [])
            if len(cols) != 1:
                raise OSIValidationError(
                    "COUNT(DISTINCT ...) must contain exactly one expression.",
                    hint="Declare separate metrics for multi-column distinct logic, or "
                    "precompute a single distinct key in the dataset.",
                )
            col_sql = cols[0].sql(dialect=dialect) if cols else "1"
            base = _sanitize(col_sql)
            return MeasureIR(
                name=f"{base}_count_distinct",
                agg=Aggregation.COUNT_DISTINCT,
                expr=col_sql,
            )
        col_sql = arg.sql(dialect=dialect)
        base = _sanitize(col_sql)
        return MeasureIR(name=f"{base}_count", agg=Aggregation.COUNT, expr=col_sql)

    for node_type, agg in _AGG_NODES.items():
        if isinstance(node, node_type):
            col_sql = node.this.sql(dialect=dialect)
            base = _sanitize(col_sql)
            return MeasureIR(name=f"{base}_{agg.value}", agg=agg, expr=col_sql)

    raise OSIValidationError(
        "expression is not a recognized aggregation.",
        hint="Declare an aggregate metric (SUM/COUNT/COUNT DISTINCT/AVG/MIN/MAX) "
        "or model this as a dataset/field instead of a metric.",
    )


def _is_aggregate(node: exp.Expression) -> bool:
    return isinstance(node, (exp.Count, *_AGG_NODES.keys()))


def _same_measure_signature(left: MeasureIR, right: MeasureIR) -> bool:
    return left.agg is right.agg and left.expr == right.expr


def _raise_measure_name_collision(name: str) -> None:
    raise OSIValidationError(
        f"aggregate expressions produce the same backing measure name `{name}`.",
        hint="Use expressions that compile to distinct measure names, or define "
        "separate metrics so the ambiguity is explicit.",
    )


def _collect_aggregate_measures(tree: exp.Expression, *, dialect: str):
    """Replace each aggregate subtree with a reference to its backing measure.

    Returns the rewritten expression tree and the de-duplicated list of measures.
    """
    measures: dict[str, MeasureIR] = {}

    def _replace(node: exp.Expression) -> exp.Expression:
        if _is_aggregate(node):
            measure = _measure_from_aggregate(node, dialect=dialect)
            existing = measures.get(measure.name)
            if existing is not None:
                if _same_measure_signature(existing, measure):
                    return exp.column(existing.name)
                _raise_measure_name_collision(measure.name)
            measures[measure.name] = measure
            return exp.column(measure.name)
        return node

    new_tree = tree.transform(_replace)
    return new_tree, list(measures.values())


def compile_metric_expression(
    name: str,
    expression: str,
    *,
    dialect: str = DEFAULT_SQLGLOT_DIALECT,
) -> MetricIR:
    """Infer a MetricIR from a single OSI metric expression.

    Handles the unambiguous single-aggregate case. Window functions and bare
    non-aggregate expressions are rejected with business-semantic errors.
    """
    try:
        tree = sqlglot.parse_one(expression, read=dialect)
    except Exception as e:  # noqa: BLE001 - surface as author-facing error
        raise OSIValidationError(
            f"could not parse expression `{expression}`.",
            metric=name,
            hint="Provide a valid SQL aggregation expression.",
        ) from e

    if tree is None:
        raise OSIValidationError(f"empty expression for metric `{name}`.", metric=name)

    # Reject window / ranking functions: these need a precomputed dataset/view.
    if isinstance(tree, exp.Window) or tree.find(exp.Window):
        raise OSIValidationError(
            "uses a window/ranking function, which cannot be modeled as a metric.",
            metric=name,
            hint="Model ranking/window results as a precomputed dataset or view.",
        )

    if _is_aggregate(tree):
        measure = _measure_from_aggregate(tree, dialect=dialect)
        return MetricIR(name=name, kind=MetricKind.AGGREGATE, measures=[measure])

    inner_aggs = list(tree.find_all(exp.AggFunc))

    # ratio: division of exactly two aggregates -> numerator / denominator
    if (
        isinstance(tree, exp.Div)
        and _is_aggregate(tree.this)
        and _is_aggregate(tree.expression)
    ):
        num = _measure_from_aggregate(tree.this, dialect=dialect)
        den = _measure_from_aggregate(tree.expression, dialect=dialect)
        if num.name == den.name and not _same_measure_signature(num, den):
            _raise_measure_name_collision(num.name)
        measures = [num] if num.name == den.name else [num, den]
        return MetricIR(
            name=name,
            kind=MetricKind.RATIO,
            measures=measures,
            numerator=num.name,
            denominator=den.name,
        )

    # bare division of named terms (no aggregates) -> ambiguous, need hints
    if isinstance(tree, exp.Div) and not inner_aggs:
        raise OSIValidationError(
            "uses division between named terms.",
            metric=name,
            hint="Please declare numerator and denominator semantic inputs.",
        )

    # other arithmetic over aggregates -> expression over backing measures
    if inner_aggs:
        new_tree, measures = _collect_aggregate_measures(tree, dialect=dialect)
        return MetricIR(
            name=name,
            kind=MetricKind.EXPRESSION,
            measures=measures,
            expression=new_tree.sql(dialect=dialect),
        )

    raise OSIValidationError(
        f"expression `{expression}` is not an aggregation and cannot be a metric.",
        metric=name,
        hint="Aggregate metrics must wrap columns in SUM/COUNT/AVG/MIN/MAX, "
        "or declare numerator/denominator for a ratio.",
    )


def _compile_dataset(ds: OSIDataset) -> DatasetIR:
    fields: list[FieldIR] = []
    identifiers: list[IdentifierIR] = []
    primary_time: Optional[str] = None

    if ds.time_dimension:
        primary_time = ds.time_dimension.name
        fields.append(
            FieldIR(
                name=ds.time_dimension.name,
                expr=ds.time_dimension.expr or ds.time_dimension.name,
                type="time",
                is_primary_time=True,
                time_granularity=ds.time_dimension.granularity,
            )
        )

    for dim in ds.dimensions:
        fields.append(
            FieldIR(
                name=dim.name,
                expr=dim.expr or dim.name,
                type=dim.type,
                time_granularity=dim.granularity,
            )
        )

    if ds.primary_key:
        keys = (
            [ds.primary_key]
            if isinstance(ds.primary_key, str)
            else list(ds.primary_key)
        )
        for key in keys:
            identifiers.append(IdentifierIR(name=key, type="primary", expr=key))

    return DatasetIR(
        name=ds.name,
        sql_table=ds.source.table,
        sql_query=ds.source.query,
        fields=fields,
        identifiers=identifiers,
        primary_time_dimension=primary_time,
    )


def _build_metric_inputs(metric: OSIMetric) -> list[MetricInputIR]:
    """Resolve a derived metric's inputs from hints or from its expression."""
    inputs: list[MetricInputIR] = []
    for item in metric.inputs:
        if isinstance(item, OSIMetricInput):
            inputs.append(
                MetricInputIR(
                    name=item.name, alias=item.alias, offset_window=item.offset_window
                )
            )
        elif isinstance(item, str):
            inputs.append(MetricInputIR(name=item))
    if inputs:
        return inputs
    # no explicit inputs: treat bare identifiers in the expression as metric refs
    if metric.expression:
        try:
            tree = sqlglot.parse_one(metric.expression, read="mysql")
            names = {c.name for c in tree.find_all(exp.Column)}
            return [MetricInputIR(name=n) for n in sorted(names)]
        except Exception:  # noqa: BLE001
            return []
    return []


def _validate_metric_metadata(metric: OSIMetric) -> dict[str, object]:
    reserved = sorted(set(metric.metadata) & _RESERVED_METRIC_METADATA_KEYS)
    if reserved:
        raise OSIValidationError(
            f"metadata uses reserved metric key(s) {reserved}.",
            metric=metric.name,
            hint="Move structural metric semantics to OSI metric fields or DATUS execution hints.",
        )
    return dict(metric.metadata)


def _compile_metric(metric: OSIMetric, *, dialect: str = DEFAULT_SQLGLOT_DIALECT) -> MetricIR:
    kind = (metric.kind or "").lower()

    if metric.period_over_period is not None:
        if kind in {"derived", "ratio"}:
            raise OSIValidationError(
                "declares period_over_period with an incompatible metric kind.",
                metric=metric.name,
                hint="Use a base aggregate expression plus DATUS period_over_period, "
                "without metric_kind derived/ratio.",
            )
        if metric.inputs:
            raise OSIValidationError(
                "declares period_over_period and metric inputs.",
                metric=metric.name,
                hint="A fixed period-over-period metric must be self-contained; "
                "remove inputs and keep only the base aggregate expression.",
            )
        if metric.numerator or metric.denominator:
            raise OSIValidationError(
                "declares period_over_period with numerator/denominator.",
                metric=metric.name,
                hint="Encode the base calculation in `expression`; do not combine "
                "period_over_period with ratio input fields.",
            )
        if metric.window or metric.grain_to_date:
            raise OSIValidationError(
                "declares period_over_period with window/grain_to_date.",
                metric=metric.name,
                hint="Period-over-period and rolling/cumulative metrics are distinct "
                "fixed metric types; define separate metrics.",
            )

    if kind == "derived":
        if not metric.expression:
            raise OSIValidationError(
                "is declared as derived but has no expression over other metrics.",
                metric=metric.name,
                hint="Provide an expression referencing other metric names.",
            )
        # A derived metric is an expression over OTHER metrics; SQL window
        # functions (LAG/LEAD/RANK/... OVER) cannot be expressed that way and do
        # not lower to a valid backend metric. Period-over-period comparisons are
        # declared via an input metric's offset_window instead.
        try:
            derived_tree = sqlglot.parse_one(metric.expression, read=dialect)
        except Exception:  # noqa: BLE001
            derived_tree = None
        if derived_tree is not None and derived_tree.find(exp.Window):
            raise OSIValidationError(
                "uses a SQL window function in a derived expression.",
                metric=metric.name,
                hint="Express period-over-period changes as a derived metric whose "
                "input declares `offset_window` (e.g. '1 month'), not LAG/OVER.",
            )
        metric_ir = MetricIR(
            name=metric.name,
            kind=MetricKind.DERIVED,
            expression=metric.expression,
            inputs=_build_metric_inputs(metric),
        )
    elif kind == "ratio" and metric.numerator and metric.denominator:
        metric_ir = MetricIR(
            name=metric.name,
            kind=MetricKind.RATIO,
            numerator=metric.numerator,
            denominator=metric.denominator,
        )
    elif metric.expression:
        metric_ir = compile_metric_expression(metric.name, metric.expression, dialect=dialect)
    else:
        raise OSIValidationError(
            "needs either an `expression` or explicit ratio numerator/denominator.",
            metric=metric.name,
            hint="Declare the metric's business expression or its numerator/denominator inputs.",
        )

    metric_ir.description = metric.description
    metric_ir.dataset = metric.dataset
    metric_ir.time_dimension = metric.time_dimension
    metric_ir.window = metric.window
    metric_ir.grain_to_date = metric.grain_to_date
    metric_ir.offset_window = metric.offset_window
    if metric.period_over_period is not None:
        metric_ir.period_over_period = PeriodOverPeriodIR(
            time_grain=metric.period_over_period.time_grain,
            offset_window=metric.period_over_period.offset_window,
            calculation=metric.period_over_period.calculation,
        )
    metric_ir.format = metric.format
    metric_ir.unit = metric.unit
    metric_ir.metadata.update(_validate_metric_metadata(metric))
    if metric.subject_path:
        metric_ir.metadata["subject_path"] = metric.subject_path
    # semi-additive: attach the non-additive dimension to the backing measure
    if metric.non_additive_dimension and metric_ir.measures:
        nad = metric.non_additive_dimension
        metric_ir.measures[0].non_additive_dimension = NonAdditiveDimensionIR(
            name=nad.name,
            window_choice=nad.window_choice,
            window_groupings=list(nad.window_groupings),
        )

    # window / grain_to_date promote an aggregate to a cumulative metric
    if metric_ir.kind is MetricKind.AGGREGATE and (
        metric.window or metric.grain_to_date
    ):
        metric_ir.kind = MetricKind.CUMULATIVE
    return metric_ir


def _namespace_measures(metric: MetricIR, prefix: str) -> None:
    """Make backing-measure names globally unique by prefixing with the dataset.

    MetricFlow requires measure names to be unique across all data sources, so
    the same aggregate on two datasets must not collide. References inside the
    metric (numerator/denominator/expression) are rewritten to match.
    """
    rename: dict[str, str] = {}
    for measure in metric.measures:
        new_name = f"{prefix}_{measure.name}"
        rename[measure.name] = new_name
        measure.name = new_name

    if metric.numerator in rename:
        metric.numerator = rename[metric.numerator]
    if metric.denominator in rename:
        metric.denominator = rename[metric.denominator]
    if metric.expression:
        for old, new in rename.items():
            metric.expression = re.sub(rf"\b{re.escape(old)}\b", new, metric.expression)


def compile_document(doc: OSIDocument, *, dialect: str = DEFAULT_SQLGLOT_DIALECT) -> SemanticModelIR:
    """Compile a parsed OSI authoring document into a SemanticModelIR."""
    datasets = [_compile_dataset(ds) for ds in doc.datasets]
    relationships = [
        RelationshipIR(
            name=rel.name,
            type=rel.type,
            from_dataset=rel.from_dataset,
            from_identifier=rel.from_identifier,
            to_dataset=rel.to_dataset,
            to_identifier=rel.to_identifier,
        )
        for rel in doc.relationships
    ]
    default_dataset = doc.datasets[0].name if doc.datasets else None
    metrics = []
    for m in doc.metrics:
        metric_ir = _compile_metric(m, dialect=dialect)
        if len(doc.datasets) > 1 and metric_ir.measures and not metric_ir.dataset:
            raise OSIValidationError(
                "metric must declare `dataset` when the semantic model has multiple datasets.",
                metric=metric_ir.name,
                hint="Set the metric's DATUS custom extension `dataset` to the dataset that owns its measures.",
            )
        prefix = metric_ir.dataset or default_dataset
        if prefix:
            _namespace_measures(metric_ir, prefix)
        metrics.append(metric_ir)
    return SemanticModelIR(
        name=doc.name, datasets=datasets, relationships=relationships, metrics=metrics
    )

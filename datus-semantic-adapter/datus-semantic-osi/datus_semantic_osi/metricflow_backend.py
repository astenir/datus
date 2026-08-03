# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""MetricFlow backend lowering: Datus Semantic IR -> legacy MetricFlow YAML.

Targets the dialect of the ``Datus-ai/metricflow`` fork: ``data_source:``
documents (with identifiers / dimensions / measures) plus separate ``metric:``
documents. The generated YAML is an artifact; users never edit it and the LLM
never produces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import (
    DatasetIR,
    IdentifierIR,
    MeasureIR,
    MetricIR,
    MetricKind,
    SemanticModelIR,
)

DEFAULT_OWNER = "datus@datus.ai"
_PERIOD_OVER_PERIOD_BASE_PREFIX = "datus_pop_base"
_RESERVED_TIME_GRAIN_NAMES = {"day", "week", "month", "quarter", "year"}
_RESERVED_DIMENSION_PREFIX = "datus_dimension_"
_STATIC_METRIC_TIME = "datus_static_metric_time"


def executable_query_source(sql: str) -> str:
    """Return authored query SQL in a form that can be embedded as a subquery."""
    return re.sub(r";\s*$", "", str(sql or ""))


def metricflow_dimension_name(name: str) -> str:
    """Map an OSI dimension name to a non-reserved MetricFlow element name."""
    value = str(name or "")
    lowered = value.lower()
    if lowered.startswith(_RESERVED_DIMENSION_PREFIX):
        return f"{_RESERVED_DIMENSION_PREFIX}{value}"
    if lowered in _RESERVED_TIME_GRAIN_NAMES:
        return f"{_RESERVED_DIMENSION_PREFIX}{value}"
    return value


def metricflow_dimension_path(name: str) -> str:
    """Map the leaf of an OSI relationship dimension path for MetricFlow."""
    value = str(name or "")
    lowered = value.lower()
    if lowered == "metric_time" or lowered.startswith("metric_time__"):
        return value
    parts = value.split("__")
    parts[-1] = metricflow_dimension_name(parts[-1])
    return "__".join(parts)


@dataclass
class MetricFlowArtifact:
    """Generated MetricFlow YAML, as structured docs plus rendered text."""

    data_source_docs: List[dict] = field(default_factory=list)
    metric_docs: List[dict] = field(default_factory=list)

    def semantic_models_yaml(self) -> str:
        return _dump_multidoc(self.data_source_docs)

    def metrics_yaml(self) -> str:
        return _dump_multidoc(self.metric_docs)

    def write(self, directory: Path) -> Dict[str, Path]:
        """Write semantic_models.yaml + metrics.yaml into *directory*."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        written: Dict[str, Path] = {}
        sm_path = directory / "semantic_models.yaml"
        sm_path.write_text(self.semantic_models_yaml(), encoding="utf-8")
        written["semantic_models"] = sm_path
        m_path = directory / "metrics.yaml"
        if self.metric_docs:
            m_path.write_text(self.metrics_yaml(), encoding="utf-8")
            written["metrics"] = m_path
        else:
            m_path.unlink(missing_ok=True)
        return written


def _dump_multidoc(docs: List[dict]) -> str:
    return "".join(
        "---\n" + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        for doc in docs
    )


def _dataset_sql(ds: DatasetIR) -> dict:
    """Render a dataset's authored table or query source."""
    if ds.sql_query:
        # MetricFlow embeds query sources inside a FROM subquery. Preserve the
        # authored OSI source, but omit its terminal statement delimiter in the
        # generated execution artifact.
        return {"sql_query": executable_query_source(ds.sql_query)}
    if ds.sql_table:
        # MetricFlow's sql_table requires a schema-qualified name
        # (``schema.table`` / ``db.schema.table``). Render bare table names as a
        # query so unqualified OSI sources still validate.
        if "." in ds.sql_table:
            return {"sql_table": ds.sql_table}
        return {"sql_query": f"SELECT * FROM {ds.sql_table}"}
    raise OSIValidationError(
        f"dataset `{ds.name}` has no table or query source.",
        hint="Declare a source table or query for the dataset.",
    )


def _lower_dimensions(ds: DatasetIR) -> List[dict]:
    dims: List[dict] = []
    for f in ds.fields:
        if not f.is_dimension:
            # Plain row-level field (no `dimension:` block in OSI core): it may
            # back metric expressions but is not exposed for grouping.
            continue
        backend_name = metricflow_dimension_name(f.name)
        if f.type == "time":
            entry: dict = {
                "name": backend_name,
                "type": "time",
                "type_params": {
                    "is_primary": bool(f.is_primary_time),
                    "time_granularity": f.time_granularity or "day",
                },
            }
        else:
            entry = {"name": backend_name, "type": "categorical"}
        expression = f.expr or f.name
        if expression != backend_name:
            entry["expr"] = expression
        dims.append(entry)
    return dims


def _lower_measure(m: MeasureIR) -> dict:
    entry = {"name": m.name, "agg": m.agg.value, "expr": m.expr, "create_metric": False}
    if m.non_additive_dimension is not None:
        nad = m.non_additive_dimension
        nad_entry: dict = {"name": nad.name, "window_choice": nad.window_choice}
        if nad.window_groupings:
            nad_entry["window_groupings"] = list(nad.window_groupings)
        entry["non_additive_dimension"] = nad_entry
    return entry


def _collect_measures_by_dataset(model: SemanticModelIR) -> Dict[str, List[MeasureIR]]:
    by_ds: Dict[str, Dict[str, MeasureIR]] = {ds.name: {} for ds in model.datasets}
    default_ds = model.datasets[0].name if model.datasets else None
    for metric in model.metrics:
        ds_name = metric.dataset or default_ds
        if ds_name is None or ds_name not in by_ds:
            raise OSIValidationError(
                f"references dataset `{metric.dataset}` which is not declared.",
                metric=metric.name,
                hint="Point the metric at one of the declared datasets.",
            )
        for measure in metric.measures:
            by_ds[ds_name][measure.name] = measure
    return {name: list(measures.values()) for name, measures in by_ds.items()}


def _time_dimension_field_names(ds: DatasetIR) -> set:
    return {f.name for f in ds.fields if f.is_dimension and f.type == "time"}


def _lower_identifier(identifier: IdentifierIR) -> dict:
    entry: dict = {"name": identifier.name, "type": identifier.type}
    if identifier.components:
        entry["identifiers"] = [
            {"name": component.name, "expr": component.expr}
            for component in identifier.components
        ]
    elif identifier.expr is not None:
        entry["expr"] = identifier.expr
    return entry


def _kept_identifiers(ds: DatasetIR, keep_names: set) -> List[dict]:
    """Dataset identifiers minus auto-resolved time-dimension collisions.

    Composite key components have scoped internal names and may reference the
    same physical expression as a time dimension. Only a scalar identifier
    whose top-level name collides with a time dimension needs this resolution:
    keep the time dimension unless a relationship explicitly joins on that
    identifier, in which case the join wins.
    """
    time_names = _time_dimension_field_names(ds)
    kept: List[dict] = []
    for i in ds.identifiers:
        if i.name in time_names and i.name not in keep_names:
            continue
        kept.append(_lower_identifier(i))
    return kept


def _identifier_shape(identifier: dict) -> tuple:
    components = tuple(
        (component.get("name"), component.get("expr"))
        for component in identifier.get("identifiers", [])
    )
    return identifier.get("expr"), components


def _append_identifier(
    identifiers: List[dict], incoming: dict, dataset_name: str
) -> None:
    existing = next(
        (
            identifier
            for identifier in identifiers
            if identifier["name"] == incoming["name"]
        ),
        None,
    )
    if existing is None:
        identifiers.append(incoming)
        return
    if _identifier_shape(existing) == _identifier_shape(incoming):
        # Preserve an authored primary/unique type over a relationship-derived
        # alias. MetricFlow accepts either as the non-fanout side of the join.
        return
    raise OSIValidationError(
        f"relationships lower to duplicate {incoming['type']} identifier "
        f"`{incoming['name']}` on dataset `{dataset_name}` with different key "
        "expressions.",
        hint="Give each relationship a distinct OSI core `name`.",
    )


def _merge_relationship_identifiers(
    authored: List[dict], relationship_identifiers: List[dict], dataset_name: str
) -> List[dict]:
    """Prefer relationship-named aliases for the same unique target key.

    OSI relationship names define the public join path. When a relationship
    targets an authored primary/unique identifier with the same key shape, the
    relationship-named unique alias is sufficient for MetricFlow and avoids
    exposing the physical key name globally as a second identifier type.
    """
    unique_aliases = [
        identifier
        for identifier in relationship_identifiers
        if identifier.get("type") in {"primary", "unique"}
    ]
    identifiers = [
        identifier
        for identifier in authored
        if not any(
            identifier.get("type") in {"primary", "unique"}
            and identifier["name"] != alias["name"]
            and _identifier_shape(identifier) == _identifier_shape(alias)
            for alias in unique_aliases
        )
    ]
    for extra in relationship_identifiers:
        _append_identifier(identifiers, extra, dataset_name)
    return identifiers


def _lower_data_source(
    ds: DatasetIR,
    measures: List[MeasureIR],
    extra_identifiers: List[dict] = None,
    keep_identifier_names: set = None,
) -> dict:
    body: dict = {"name": ds.name, "description": ds.name, "owners": [DEFAULT_OWNER]}
    body.update(_dataset_sql(ds))
    identifiers = _merge_relationship_identifiers(
        _kept_identifiers(ds, keep_identifier_names or set()),
        extra_identifiers or [],
        ds.name,
    )
    if identifiers:
        body["identifiers"] = identifiers
    # MetricFlow forbids one element being both an identifier and a dimension.
    # Drop dimensions whose name collides with an identifier (e.g. a primary key
    # the author also listed as a dimension).
    identifier_names = {i["name"] for i in identifiers}
    dims = [d for d in _lower_dimensions(ds) if d["name"] not in identifier_names]
    if measures and not any(
        dimension.get("type") == "time"
        and dimension.get("type_params", {}).get("is_primary")
        for dimension in dims
    ):
        # MetricFlow requires every measure to have an aggregation-time
        # dimension, while OSI permits timeless snapshot / pre-aggregated
        # datasets. Add an execution-only constant dimension rather than
        # changing the authored dataset or exposing a fabricated public field.
        name = _STATIC_METRIC_TIME
        existing_names = identifier_names | {dimension["name"] for dimension in dims}
        while name in existing_names:
            name = f"{name}_internal"
        dims.append(
            {
                "name": name,
                "type": "time",
                "type_params": {
                    "is_primary": True,
                    "time_granularity": "day",
                },
                "expr": "CAST('1970-01-01' AS DATE)",
            }
        )
    if dims:
        body["dimensions"] = dims
    if measures:
        body["measures"] = [_lower_measure(m) for m in measures]
    return {"data_source": body}


def _lower_metric(metric: MetricIR) -> dict:
    if metric.period_over_period is not None:
        return _lower_period_over_period_metric(metric)

    body: dict = {"name": metric.name, "owners": [DEFAULT_OWNER]}
    if metric.description:
        body["description"] = metric.description

    if metric.kind is MetricKind.AGGREGATE:
        body["type"] = "measure_proxy"
        body["type_params"] = {"measures": [metric.measures[0].name]}
    elif metric.kind is MetricKind.RATIO:
        body["type"] = "ratio"
        body["type_params"] = {
            "numerator": metric.numerator,
            "denominator": metric.denominator,
        }
    elif metric.kind is MetricKind.EXPRESSION:
        body["type"] = "expr"
        body["type_params"] = {
            "expr": metric.expression,
            "measures": [m.name for m in metric.measures],
        }
    elif metric.kind is MetricKind.CUMULATIVE:
        body["type"] = "cumulative"
        type_params: dict = {"measures": [m.name for m in metric.measures]}
        if metric.window:
            type_params["window"] = metric.window
        if metric.grain_to_date:
            type_params["grain_to_date"] = metric.grain_to_date
        body["type_params"] = type_params
    elif metric.kind is MetricKind.DERIVED:
        body["type"] = "derived"
        input_metrics = []
        for inp in metric.inputs:
            entry: dict = {"name": inp.name}
            if inp.alias:
                entry["alias"] = inp.alias
            if inp.offset_window:
                entry["offset_window"] = inp.offset_window
            input_metrics.append(entry)
        body["type_params"] = {"expr": metric.expression, "metrics": input_metrics}
    else:  # pragma: no cover - all MetricKind values handled above
        raise OSIValidationError(
            f"metric kind `{metric.kind.value}` is not supported by the MetricFlow backend yet.",
            metric=metric.name,
        )

    return {"metric": body}


def period_over_period_base_metric_name(metric: MetricIR) -> str:
    return f"{_PERIOD_OVER_PERIOD_BASE_PREFIX}_{metric.name}"


def is_period_over_period_base_metric_name(metric_name: str) -> bool:
    return str(metric_name).startswith(f"{_PERIOD_OVER_PERIOD_BASE_PREFIX}_")


def _period_over_period_expression(
    metric_name: str, previous_alias: str, calculation: str
) -> str:
    if calculation == "previous_value":
        return previous_alias
    if calculation == "delta":
        return f"{metric_name} - {previous_alias}"
    if calculation == "percent_change":
        return f"({metric_name} - {previous_alias}) / NULLIF({previous_alias}, 0)"
    if calculation == "ratio":
        return f"{metric_name} / NULLIF({previous_alias}, 0)"
    raise OSIValidationError(
        f"unsupported period_over_period calculation `{calculation}`.",
        hint="Supported calculations: previous_value, delta, percent_change, ratio.",
    )


def _lower_period_over_period_metric(metric: MetricIR) -> dict:
    pop = metric.period_over_period
    if pop is None:  # pragma: no cover - caller guards this
        raise OSIValidationError(
            "period_over_period metric is missing semantics.", metric=metric.name
        )
    base_name = period_over_period_base_metric_name(metric)
    previous_alias = f"{base_name}_previous"
    metric_inputs = [
        {
            "name": base_name,
            "alias": previous_alias,
            "offset_window": pop.offset_window,
        }
    ]
    if pop.calculation != "previous_value":
        metric_inputs.insert(0, {"name": base_name})
    body: dict = {
        "name": metric.name,
        "owners": [DEFAULT_OWNER],
        "type": "derived",
        "type_params": {
            "metrics": metric_inputs,
            "expr": _period_over_period_expression(
                base_name, previous_alias, pop.calculation
            ),
        },
    }
    if metric.description:
        body["description"] = metric.description
    return {"metric": body}


def _relationship_identifiers(model: SemanticModelIR) -> Dict[str, List[dict]]:
    """Materialize many-to-one relationships as MetricFlow join identifiers.

    Each relationship creates the same identifier name and component names on
    both sides. Local expressions may differ; MetricFlow correlates composite
    components by their shared names.
    """
    datasets = {ds.name: ds for ds in model.datasets}
    extras: Dict[str, List[dict]] = {ds.name: [] for ds in model.datasets}

    def relationship_identifier(
        rel,
        dataset: DatasetIR,
        columns: List[str],
        identifier_type: str,
    ) -> dict:
        field_expr = {field.name: field.expr for field in dataset.fields}
        if len(columns) == 1:
            column = columns[0]
            return {
                "name": rel.name,
                "type": identifier_type,
                "expr": field_expr.get(column, column),
            }
        return {
            "name": rel.name,
            "type": identifier_type,
            "identifiers": [
                {
                    "name": f"{rel.name}_key_{index}",
                    "expr": field_expr.get(column, column),
                }
                for index, column in enumerate(columns, start=1)
            ],
        }

    for rel in model.relationships:
        from_dataset = datasets.get(rel.from_dataset)
        to_dataset = datasets.get(rel.to_dataset)
        if from_dataset is None or to_dataset is None:
            continue
        _append_identifier(
            extras.setdefault(rel.from_dataset, []),
            relationship_identifier(rel, from_dataset, rel.from_columns, "foreign"),
            rel.from_dataset,
        )
        _append_identifier(
            extras.setdefault(rel.to_dataset, []),
            relationship_identifier(rel, to_dataset, rel.to_columns, "unique"),
            rel.to_dataset,
        )
    return extras


def _relationship_used_identifier_names(model: SemanticModelIR) -> Dict[str, set]:
    """Identifier names each dataset must keep because a relationship joins on them."""
    used: Dict[str, set] = {ds.name: set() for ds in model.datasets}
    for rel in model.relationships:
        used.setdefault(rel.to_dataset, set()).add(rel.name)
        used.setdefault(rel.from_dataset, set()).add(rel.name)
    return used


def lowered_element_types(model: SemanticModelIR) -> Dict[str, set]:
    """Element name -> MetricFlow element types the lowering will emit.

    Mirrors ``lower_to_metricflow`` exactly (identifier auto-resolution,
    relationship-derived foreign identifiers, same-dataset collision shadowing,
    non-dimension fields) so validation reports precisely the conflicts the
    backend would reject.
    """
    used = _relationship_used_identifier_names(model)
    rel_extras = _relationship_identifiers(model)
    element_type: Dict[str, set] = {}
    for ds in model.datasets:
        identifiers = _merge_relationship_identifiers(
            _kept_identifiers(ds, used.get(ds.name, set())),
            rel_extras.get(ds.name, []),
            ds.name,
        )
        identifier_names = {entry["name"] for entry in identifiers}
        for name in identifier_names:
            element_type.setdefault(name, set()).add("identifier")
        for f in ds.fields:
            if not f.is_dimension or f.name in identifier_names:
                continue
            element_type.setdefault(f.name, set()).add(
                "time" if f.type == "time" else "dimension"
            )
    return element_type


def lower_to_metricflow(model: SemanticModelIR) -> MetricFlowArtifact:
    """Lower a SemanticModelIR into MetricFlow YAML documents."""
    measures_by_ds = _collect_measures_by_dataset(model)
    rel_identifiers = _relationship_identifiers(model)
    rel_used = _relationship_used_identifier_names(model)
    artifact = MetricFlowArtifact()
    for ds in model.datasets:
        document = _lower_data_source(
            ds,
            measures_by_ds.get(ds.name, []),
            rel_identifiers.get(ds.name, []),
            rel_used.get(ds.name, set()),
        )
        body = document["data_source"]
        if not any(
            body.get(element_type)
            for element_type in ("identifiers", "dimensions", "measures")
        ):
            # A staged query-backed dataset may contain only future metric
            # outputs. MetricFlow cannot instantiate an element-free source;
            # omit it until a metric contributes a backing measure.
            continue
        artifact.data_source_docs.append(document)
    for metric in model.metrics:
        if metric.period_over_period is not None:
            base_metric = metric.model_copy(
                update={
                    "name": period_over_period_base_metric_name(metric),
                    "description": "",
                    "period_over_period": None,
                }
            )
            artifact.metric_docs.append(_lower_metric(base_metric))
        artifact.metric_docs.append(_lower_metric(metric))
    return artifact

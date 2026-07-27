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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import (
    DatasetIR,
    MeasureIR,
    MetricIR,
    MetricKind,
    SemanticModelIR,
)

DEFAULT_OWNER = "datus@datus.ai"
_PERIOD_OVER_PERIOD_BASE_PREFIX = "datus_pop_base"


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
        return {"sql_query": ds.sql_query}
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
        if f.type == "time":
            entry: dict = {
                "name": f.name,
                "type": "time",
                "type_params": {
                    "is_primary": bool(f.is_primary_time),
                    "time_granularity": f.time_granularity or "day",
                },
            }
        else:
            entry = {"name": f.name, "type": "categorical"}
        if f.expr and f.expr != f.name:
            entry["expr"] = f.expr
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


def _kept_identifiers(ds: DatasetIR, keep_names: set) -> List[dict]:
    """Dataset identifiers minus auto-resolved time-dimension collisions.

    A snapshot-table key component that doubles as the dataset's time dimension
    (e.g. a monthly ``etl_dt`` inside a composite primary key) is legal in OSI
    core but MetricFlow forbids one element being both an identifier and a
    dimension. Keep the time dimension and drop the identifier, unless a
    relationship joins on it — then the join wins and the dimension is dropped
    by the existing collision rule instead.
    """
    time_names = _time_dimension_field_names(ds)
    kept: List[dict] = []
    for i in ds.identifiers:
        if i.name in time_names and i.name not in keep_names:
            continue
        kept.append({"name": i.name, "type": i.type, "expr": i.expr})
    return kept


def _lower_data_source(
    ds: DatasetIR,
    measures: List[MeasureIR],
    extra_identifiers: List[dict] = None,
    keep_identifier_names: set = None,
) -> dict:
    body: dict = {"name": ds.name, "description": ds.name, "owners": [DEFAULT_OWNER]}
    body.update(_dataset_sql(ds))
    identifiers = _kept_identifiers(ds, keep_identifier_names or set())
    for extra in extra_identifiers or []:
        if not any(existing["name"] == extra["name"] for existing in identifiers):
            identifiers.append(extra)
    if identifiers:
        body["identifiers"] = identifiers
    # MetricFlow forbids one element being both an identifier and a dimension.
    # Drop dimensions whose name collides with an identifier (e.g. a primary key
    # the author also listed as a dimension).
    identifier_names = {i["name"] for i in identifiers}
    dims = [d for d in _lower_dimensions(ds) if d["name"] not in identifier_names]
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


def _period_over_period_expression(metric_name: str, previous_alias: str, calculation: str) -> str:
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
        raise OSIValidationError("period_over_period metric is missing semantics.", metric=metric.name)
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
            "expr": _period_over_period_expression(base_name, previous_alias, pop.calculation),
        },
    }
    if metric.description:
        body["description"] = metric.description
    return {"metric": body}


def _relationship_identifiers(model: SemanticModelIR) -> Dict[str, List[dict]]:
    """Materialize many-to-one relationships as MetricFlow join identifiers.

    A relationship becomes a foreign identifier on the "from" dataset whose name
    matches the "to" dataset's primary identifier, so MetricFlow can join them.
    """
    primary_name_by_ds: Dict[str, str] = {}
    for ds in model.datasets:
        primary = next((i for i in ds.identifiers if i.type == "primary"), None)
        if primary:
            primary_name_by_ds[ds.name] = primary.name

    extras: Dict[str, List[dict]] = {ds.name: [] for ds in model.datasets}
    for rel in model.relationships:
        join_name = primary_name_by_ds.get(rel.to_dataset, rel.to_identifier)
        dataset_extras = extras.setdefault(rel.from_dataset, [])
        existing = next(
            (item for item in dataset_extras if item["name"] == join_name), None
        )
        if existing is not None:
            if existing["expr"] != rel.from_identifier:
                raise OSIValidationError(
                    "relationships lower to duplicate foreign identifier "
                    f"`{join_name}` on dataset `{rel.from_dataset}` with "
                    f"different expressions `{existing['expr']}` and "
                    f"`{rel.from_identifier}`.",
                    hint="Give the target datasets distinct primary identifier names "
                    "or split the relationship roles into separate datasets.",
                )
            continue
        dataset_extras.append(
            {"name": join_name, "type": "foreign", "expr": rel.from_identifier}
        )
    return extras


def _relationship_used_identifier_names(model: SemanticModelIR) -> Dict[str, set]:
    """Identifier names each dataset must keep because a relationship joins on them."""
    primary_name_by_ds: Dict[str, str] = {}
    for ds in model.datasets:
        primary = next((i for i in ds.identifiers if i.type == "primary"), None)
        if primary:
            primary_name_by_ds[ds.name] = primary.name

    used: Dict[str, set] = {ds.name: set() for ds in model.datasets}
    for rel in model.relationships:
        join_name = primary_name_by_ds.get(rel.to_dataset, rel.to_identifier)
        used.setdefault(rel.to_dataset, set()).update({join_name, rel.to_identifier})
        used.setdefault(rel.from_dataset, set()).add(rel.from_identifier)
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
        identifier_names = {
            entry["name"] for entry in _kept_identifiers(ds, used.get(ds.name, set()))
        }
        identifier_names.update(
            extra["name"] for extra in rel_extras.get(ds.name, [])
        )
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
        artifact.data_source_docs.append(
            _lower_data_source(
                ds,
                measures_by_ds.get(ds.name, []),
                rel_identifiers.get(ds.name, []),
                rel_used.get(ds.name, set()),
            )
        )
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

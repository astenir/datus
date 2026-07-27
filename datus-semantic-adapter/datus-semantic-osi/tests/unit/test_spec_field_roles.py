# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""OSI core field-role semantics: `dimension:` block opt-in, unique_keys,
snapshot-table identifier auto-resolution, and structural validation.

Anchored on a monthly branch loan-quality snapshot table shape: a composite primary key that includes the time dimension, code columns
used for grouping, and numeric columns that only back metric aggregations.
"""

import yaml

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.metricflow_backend import lower_to_metricflow, lowered_element_types
from datus_semantic_osi.profile import parse_osi_model as parse_osi
from datus_semantic_osi.profile import to_core_schema_document
from datus_semantic_osi.validator import (
    detect_measure_columns_modeled_as_dimensions,
    validate_ir,
)


def _field(name, *, dimension=None, hints=None):
    entry = {
        "name": name,
        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": name}]},
    }
    if dimension is not None:
        entry["dimension"] = dimension
    if hints:
        import json

        entry["custom_extensions"] = [{"vendor_name": "DATUS", "data": json.dumps(hints)}]
    return entry


def _core_doc(datasets, metrics=None, relationships=None):
    model = {"name": "lending", "datasets": datasets}
    if relationships:
        model["relationships"] = relationships
    if metrics:
        model["metrics"] = metrics
    return {"version": "0.2.0.dev0", "semantic_model": [model]}


def _snapshot_dataset(name="loan_quality", primary_key=None, extra_fields=None):
    fields = [
        _field("etl_dt", dimension={"is_time": True}, hints={"time_granularity": "month"}),
        _field("org_name", dimension={"is_time": False}),
        _field("loan_balance"),  # plain row-level field: no dimension block
    ]
    fields.extend(extra_fields or [])
    ds = {"name": name, "source": "dm.loan_quality", "fields": fields}
    if primary_key:
        ds["primary_key"] = primary_key
    return ds


def _sum_metric(name="loan_balance_total", dataset="loan_quality", column="loan_balance"):
    return {
        "name": name,
        "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": f"SUM({column})"}]},
        "custom_extensions": [
            {"vendor_name": "DATUS", "data": f'{{"dataset": "{dataset}", "time_dimension": "etl_dt"}}'}
        ],
    }


class TestDimensionBlockOptIn:
    def test_field_without_dimension_block_is_not_a_dimension(self):
        doc = parse_osi(_core_doc([_snapshot_dataset()]))
        model = compile_document(doc)
        fields = {f.name: f for f in model.datasets[0].fields}
        assert fields["org_name"].is_dimension is True
        assert fields["loan_balance"].is_dimension is False
        assert fields["etl_dt"].is_dimension is True

    def test_legacy_type_hint_still_marks_a_dimension(self):
        # Old authoring carried `{"type": ...}` hints instead of dimension blocks.
        ds = _snapshot_dataset(extra_fields=[_field("legacy_code", hints={"type": "categorical"})])
        model = compile_document(parse_osi(_core_doc([ds])))
        fields = {f.name: f for f in model.datasets[0].fields}
        assert fields["legacy_code"].is_dimension is True

    def test_non_dimension_field_is_not_lowered_as_dimension(self):
        doc = parse_osi(_core_doc([_snapshot_dataset()], metrics=[_sum_metric()]))
        art = lower_to_metricflow(compile_document(doc))
        ds = art.data_source_docs[0]["data_source"]
        dim_names = {d["name"] for d in ds.get("dimensions", [])}
        assert "org_name" in dim_names
        assert "loan_balance" not in dim_names
        # the measure still aggregates the raw column
        assert any(m["expr"] == "loan_balance" for m in ds["measures"])

    def test_round_trip_preserves_non_dimension_fields(self):
        doc = parse_osi(_core_doc([_snapshot_dataset()]))
        core = to_core_schema_document(doc)
        reloaded = compile_document(parse_osi(core))
        fields = {f.name: f for f in reloaded.datasets[0].fields}
        assert fields["loan_balance"].is_dimension is False
        assert fields["org_name"].is_dimension is True


class TestUniqueKeys:
    def test_single_column_unique_key_becomes_unique_identifier(self):
        ds = _snapshot_dataset(primary_key=["org_no"])
        ds["unique_keys"] = [["org_code"], ["etl_dt", "org_no"]]
        model = compile_document(parse_osi(_core_doc([ds])))
        idents = {i.name: i.type for i in model.datasets[0].identifiers}
        assert idents["org_no"] == "primary"
        assert idents["org_code"] == "unique"
        # composite unique keys have no single-identifier representation
        assert "etl_dt" not in idents

    def test_unique_keys_survive_core_round_trip(self):
        ds = _snapshot_dataset()
        ds["unique_keys"] = [["org_code"]]
        doc = parse_osi(_core_doc([ds]))
        core = to_core_schema_document(doc)
        assert core["semantic_model"][0]["datasets"][0]["unique_keys"] == [["org_code"]]


class TestSnapshotIdentifierAutoResolution:
    """A composite PK containing the time dimension is OSI-legal; the lowering
    resolves the MetricFlow identifier/dimension conflict instead of erroring."""

    def _snapshot_model(self):
        ds = _snapshot_dataset(primary_key=["etl_dt", "org_no"])
        ds["fields"].append(_field("org_no", dimension={"is_time": False}))
        return compile_document(parse_osi(_core_doc([ds], metrics=[_sum_metric()])))

    def test_time_dimension_wins_over_unjoined_pk_component(self):
        art = lower_to_metricflow(self._snapshot_model())
        ds = art.data_source_docs[0]["data_source"]
        ident_names = {i["name"] for i in ds.get("identifiers", [])}
        assert "etl_dt" not in ident_names, "time-dimension PK component must be auto-dropped"
        assert "org_no" in ident_names
        time_dims = [d for d in ds["dimensions"] if d["name"] == "etl_dt"]
        assert time_dims and time_dims[0]["type"] == "time"
        assert time_dims[0]["type_params"]["is_primary"] is True

    def test_validate_ir_reports_no_conflict_for_snapshot_shape(self):
        issues = validate_ir(self._snapshot_model())
        assert issues == []

    def test_joined_time_key_is_kept_as_identifier(self):
        fact = _snapshot_dataset(name="fact", primary_key=["etl_dt", "org_no"])
        fact["fields"].append(_field("org_no", dimension={"is_time": False}))
        dim_ds = {
            "name": "calendar",
            "source": "dm.calendar",
            "primary_key": ["etl_dt"],
            "fields": [_field("etl_dt", dimension={"is_time": True})],
        }
        rel = {
            "name": "fact_to_calendar",
            "from": "fact",
            "to": "calendar",
            "from_columns": ["etl_dt"],
            "to_columns": ["etl_dt"],
        }
        model = compile_document(parse_osi(_core_doc([fact, dim_ds], relationships=[rel])))
        art = lower_to_metricflow(model)
        calendar = next(
            d["data_source"] for d in art.data_source_docs if d["data_source"]["name"] == "calendar"
        )
        ident_names = {i["name"] for i in calendar.get("identifiers", [])}
        assert "etl_dt" in ident_names, "join target key must not be auto-dropped"
        # and the colliding dimension is shadowed by the existing rule
        dim_names = {d["name"] for d in calendar.get("dimensions", [])}
        assert "etl_dt" not in dim_names

    def test_dataset_without_any_identifier_lowers_cleanly(self):
        doc = parse_osi(_core_doc([_snapshot_dataset()], metrics=[_sum_metric()]))
        art = lower_to_metricflow(compile_document(doc))
        ds = art.data_source_docs[0]["data_source"]
        assert "identifiers" not in ds
        assert yaml.safe_load(art.semantic_models_yaml().split("---")[1])


class TestStructuralValidation:
    def test_cross_dataset_conflict_gets_structural_guidance(self):
        ds_a = _snapshot_dataset(name="a", primary_key=["org_no"])
        ds_b = _snapshot_dataset(name="b")
        ds_b["fields"].append(_field("org_no", dimension={"is_time": False}))
        model = compile_document(parse_osi(_core_doc([ds_a, ds_b])))
        issues = validate_ir(model)
        assert len(issues) == 1
        assert "`org_no`" in issues[0]
        assert "Fix structurally" in issues[0]
        assert "dimension:" in issues[0]

    def test_relationship_lowering_failure_surfaces_as_issue_not_exception(self):
        # Two relationships lower to the same foreign identifier name with
        # different expressions; validate_ir must report it, not raise.
        fact = _snapshot_dataset(name="fact")
        fact["fields"].extend(
            [_field("a_id", dimension={"is_time": False}), _field("b_id", dimension={"is_time": False})]
        )
        dim_a = {"name": "dim_a", "source": "dm.a", "primary_key": ["id"], "fields": []}
        dim_b = {"name": "dim_b", "source": "dm.b", "primary_key": ["id"], "fields": []}
        rels = [
            {"name": "f2a", "from": "fact", "to": "dim_a", "from_columns": ["a_id"], "to_columns": ["id"]},
            {"name": "f2b", "from": "fact", "to": "dim_b", "from_columns": ["b_id"], "to_columns": ["id"]},
        ]
        model = compile_document(parse_osi(_core_doc([fact, dim_a, dim_b], relationships=rels)))
        issues = validate_ir(model)
        assert issues, "expected the duplicate foreign identifier to be reported"
        assert any("duplicate foreign identifier" in issue for issue in issues)

    def test_lowered_element_types_mirrors_lowering(self):
        ds = _snapshot_dataset(primary_key=["etl_dt", "org_no"])
        ds["fields"].append(_field("org_no", dimension={"is_time": False}))
        model = compile_document(parse_osi(_core_doc([ds])))
        types = lowered_element_types(model)
        assert types["etl_dt"] == {"time"}
        assert types["org_no"] == {"identifier"}
        assert "loan_balance" not in types


class TestQualifiedColumnResolution:
    """OSI core metric expressions qualify columns with the dataset name."""

    def _two_dataset_doc(self, metric_expr):
        loans = _snapshot_dataset(name="loans")
        deposits = _snapshot_dataset(name="deposits")
        deposits["fields"] = [_field("dep_bal")]
        metric = {
            "name": "loan_total",
            "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": metric_expr}]},
        }
        return parse_osi(_core_doc([loans, deposits], metrics=[metric]))

    def test_dataset_inferred_from_qualified_columns(self):
        model = compile_document(self._two_dataset_doc("SUM(loans.loan_balance)"))
        metric = model.metrics[0]
        assert metric.dataset == "loans"
        # the qualifier must not leak into the backing measure expression
        assert metric.measures[0].expr == "loan_balance"

    def test_unqualified_columns_in_multi_dataset_model_still_require_hint(self):
        import pytest

        from datus_semantic_osi.errors import OSIValidationError

        with pytest.raises(OSIValidationError, match="must declare `dataset`"):
            compile_document(self._two_dataset_doc("SUM(loan_balance)"))

    def test_explicit_dataset_hint_conflicting_with_qualifier_is_rejected(self):
        import pytest

        from datus_semantic_osi.errors import OSIValidationError

        loans = _snapshot_dataset(name="loans")
        deposits = _snapshot_dataset(name="deposits")
        deposits["fields"] = [_field("dep_bal")]
        metric = {
            "name": "loan_total",
            "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(loans.loan_balance)"}]},
            "custom_extensions": [{"vendor_name": "DATUS", "data": '{"dataset": "deposits"}'}],
        }
        doc = parse_osi(_core_doc([loans, deposits], metrics=[metric]))
        with pytest.raises(OSIValidationError, match="qualifies\\s+columns with dataset `loans`"):
            compile_document(doc)

    def test_qualifier_stripping_applies_to_single_dataset_models_too(self):
        metric = {
            "name": "loan_total",
            "expression": {
                "dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(loan_quality.loan_balance)"}]
            },
        }
        model = compile_document(parse_osi(_core_doc([_snapshot_dataset()], metrics=[metric])))
        assert model.metrics[0].measures[0].expr == "loan_balance"


class TestRelationshipTypeInference:
    def test_unique_from_side_key_upgrades_to_one_to_one(self):
        profile = {
            "name": "orders_extension",
            "source": "dm.orders_ext",
            "primary_key": ["order_id"],
            "fields": [_field("order_id", dimension={"is_time": False})],
        }
        orders = {
            "name": "orders",
            "source": "dm.orders",
            "primary_key": ["order_id"],
            "fields": [_field("order_id", dimension={"is_time": False})],
        }
        rel = {
            "name": "ext_to_orders",
            "from": "orders_extension",
            "to": "orders",
            "from_columns": ["order_id"],
            "to_columns": ["order_id"],
        }
        model = compile_document(parse_osi(_core_doc([profile, orders], relationships=[rel])))
        assert model.relationships[0].type == "one_to_one"

    def test_non_unique_from_side_key_stays_many_to_one(self):
        fact = _snapshot_dataset(name="fact")
        fact["fields"].append(_field("org_no", dimension={"is_time": False}))
        dim_ds = {
            "name": "org",
            "source": "dm.org",
            "primary_key": ["org_no"],
            "fields": [_field("org_no", dimension={"is_time": False})],
        }
        rel = {
            "name": "fact_to_org",
            "from": "fact",
            "to": "org",
            "from_columns": ["org_no"],
            "to_columns": ["org_no"],
        }
        model = compile_document(parse_osi(_core_doc([fact, dim_ds], relationships=[rel])))
        assert model.relationships[0].type == "many_to_one"


class TestAuthoringSpecText:
    def test_spec_text_renders_configured_dialect_and_strips_license(self):
        from datus_semantic_osi.profile import CORE_SCHEMA_VERSION
        from datus_semantic_osi.authoring_spec import authoring_spec_text

        text = authoring_spec_text("GREENPLUM")
        assert f"version: {CORE_SCHEMA_VERSION}" in text
        assert '- "GREENPLUM"' in text
        # the spec's own dialect enum is collapsed to the configured dialect
        for other in ("SNOWFLAKE", "MDX", "TABLEAU", "MAQL", "BIGQUERY"):
            assert f'- "{other}"' not in text
        assert "Licensed to the Apache Software Foundation" not in text
        # authoritative field semantics travel verbatim
        assert "grouping, filtering, and metric expressions" in text
        assert "unique_keys" in text
        assert "Datus execution subset notes" in text
        assert "exactly one column" in text


class TestMeasureAsDimensionWarning:
    def test_warns_when_aggregated_column_is_also_a_dimension(self):
        ds = _snapshot_dataset()
        ds["fields"] = [
            _field("etl_dt", dimension={"is_time": True}),
            _field("loan_balance", dimension={"is_time": False}),
        ]
        model = compile_document(parse_osi(_core_doc([ds], metrics=[_sum_metric()])))
        warnings = detect_measure_columns_modeled_as_dimensions(model)
        assert len(warnings) == 1
        assert "`loan_balance`" in warnings[0]
        assert "dimension" in warnings[0]

    def test_silent_when_aggregated_column_is_a_plain_field(self):
        model = compile_document(parse_osi(_core_doc([_snapshot_dataset()], metrics=[_sum_metric()])))
        assert detect_measure_columns_modeled_as_dimensions(model) == []

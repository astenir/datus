# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Strict OSI core authoring loader plus Datus executable profile conversion.

External YAML must conform to the official OSI core schema. Datus-only execution
hints are read from ``custom_extensions`` entries whose ``vendor_name`` is
``DATUS``; the compiler continues to operate on the internal profile models
below.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator

from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.window_semantics import WINDOW_AGGREGATION_METADATA_KEYS

DATUS_VENDOR = "DATUS"
CORE_SCHEMA_VERSION = "0.2.0.dev0"
CORE_SCHEMA_RESOURCE = "osi-core-0.2.0.dev0.schema.json"
DEFAULT_DIALECT = "ANSI_SQL"
_DISALLOWED_DATUS_HINT_KEYS = {"filter", "filters"}
_DATASET_DATUS_HINT_KEYS = {"source", "source_type", "time_dimension"}
_FIELD_DATUS_HINT_KEYS = {"type", "time_granularity", "granularity"}
_RELATIONSHIP_DATUS_HINT_KEYS = {"type"}
_METRIC_METADATA_HINT_KEYS = set(WINDOW_AGGREGATION_METADATA_KEYS) | {
    "base_metric_name",
    "time_grain",
    "time_granularity",
    "window_order_by",
    "window_frame",
}
_METRIC_DATUS_HINT_KEYS = {
    "metric_kind",
    "metric_type",
    "numerator",
    "denominator",
    "inputs",
    "dataset",
    "time_dimension",
    "window",
    "grain_to_date",
    "offset_window",
    "subject_path",
    "format",
    "unit",
    "non_additive_dimension",
    "period_over_period",
    "metadata",
    # SaaS-injected identity/ownership hints; allowed through validation, not lowered to IR.
    "uid",
    "owner",
} | _METRIC_METADATA_HINT_KEYS


class OSISource(BaseModel):
    """Where a dataset's rows come from: a physical table or a SQL query."""

    table: Optional[str] = None
    query: Optional[str] = None


class OSIDimension(BaseModel):
    name: str
    expr: Optional[str] = None
    type: str = "categorical"  # categorical | time | numeric
    granularity: Optional[str] = None
    description: Optional[str] = None
    ai_context: Optional[Union[str, Dict[str, Any]]] = None


class OSITimeDimension(BaseModel):
    name: str
    expr: Optional[str] = None
    granularity: str = "day"
    ai_context: Optional[Union[str, Dict[str, Any]]] = None


class OSIDataset(BaseModel):
    name: str
    source: OSISource
    description: Optional[str] = None
    ai_context: Optional[Union[str, Dict[str, Any]]] = None
    primary_key: Optional[Union[str, List[str]]] = None
    time_dimension: Optional[OSITimeDimension] = None
    dimensions: List[OSIDimension] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_nested_relationships(cls, data: Any) -> Any:
        if isinstance(data, dict) and "relationships" in data:
            name = f" `{data.get('name')}`" if data.get("name") else ""
            raise ValueError(
                f"Dataset{name} declares `relationships` inside the dataset; OSI "
                "core relationships must be declared once at the top-level "
                "`relationships:` list using `from`, `to`, `from_columns`, and "
                "`to_columns`."
            )
        return data


class OSIMetricInput(BaseModel):
    name: str
    alias: Optional[str] = None
    offset_window: Optional[str] = None


class OSINonAdditiveDimension(BaseModel):
    name: str
    window_choice: str = "max"  # min | max
    window_groupings: List[str] = Field(default_factory=list)


class OSIPeriodOverPeriod(BaseModel):
    time_grain: Literal["day", "week", "month", "quarter", "year"]
    offset_window: str
    calculation: Literal["previous_value", "delta", "percent_change", "ratio"]


class OSIMetric(BaseModel):
    name: str
    description: str = ""
    ai_context: Optional[Union[str, Dict[str, Any]]] = None
    expression: Optional[str] = None
    metric_kind: Optional[str] = None
    metric_type: Optional[str] = None  # compatibility alias for metric_kind
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    inputs: List[Union[str, OSIMetricInput]] = Field(default_factory=list)
    dataset: Optional[str] = None
    time_dimension: Optional[str] = None
    window: Optional[str] = None
    grain_to_date: Optional[str] = None
    offset_window: Optional[str] = None
    subject_path: Optional[List[str]] = None
    format: Optional[str] = None
    unit: Optional[str] = None
    non_additive_dimension: Optional[OSINonAdditiveDimension] = None
    period_over_period: Optional[OSIPeriodOverPeriod] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def kind(self) -> Optional[str]:
        return self.metric_kind or self.metric_type


class OSIRelationship(BaseModel):
    """Join relationship between datasets.

    OSI core declares relationships with ``from`` / ``to`` and
    ``from_columns`` / ``to_columns``. The executable Datus IR currently uses a
    single identifier on each side, so this profile accepts the OSI core shape
    and normalizes one-column relationships into the internal field names.
    Legacy top-level Datus fields remain accepted for backward compatibility.
    """

    name: str
    type: str = "many_to_one"  # many_to_one | one_to_one
    from_dataset: str
    from_identifier: str
    to_dataset: str
    to_identifier: str
    ai_context: Optional[Union[str, Dict[str, Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_osi_core_relationship(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        rel_name = normalized.get("name")

        forbidden = [
            key for key in ("join_on", "from_column", "to_column") if key in normalized
        ]
        if forbidden:
            name = f" `{rel_name}`" if rel_name else ""
            raise ValueError(
                f"Relationship{name} uses non-OSI field(s) {forbidden}; use "
                "top-level OSI core fields `from`, `to`, `from_columns`, and "
                "`to_columns`."
            )

        if "from_dataset" not in normalized and "from" in normalized:
            normalized["from_dataset"] = normalized["from"]
        if "to_dataset" not in normalized and "to" in normalized:
            normalized["to_dataset"] = normalized["to"]
        if "from_identifier" not in normalized and "from_columns" in normalized:
            normalized["from_identifier"] = _single_relationship_column(
                normalized["from_columns"], "from_columns", rel_name
            )
        if "to_identifier" not in normalized and "to_columns" in normalized:
            normalized["to_identifier"] = _single_relationship_column(
                normalized["to_columns"], "to_columns", rel_name
            )
        return normalized


class OSIDocument(BaseModel):
    name: str = "datus_semantic_model"
    datasets: List[OSIDataset] = Field(default_factory=list)
    relationships: List[OSIRelationship] = Field(default_factory=list)
    metrics: List[OSIMetric] = Field(default_factory=list)


@lru_cache(maxsize=1)
def osi_core_schema() -> Dict[str, Any]:
    """Return the bundled official OSI core JSON Schema."""
    schema_path = resources.files("datus_semantic_osi.schema").joinpath(
        CORE_SCHEMA_RESOURCE
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _json_schema_path(path: Any) -> str:
    if not path:
        return "$"
    result = "$"
    for item in path:
        if isinstance(item, int):
            result += f"[{item}]"
        else:
            result += f".{item}"
    return result


def validate_osi_core_schema(data: Dict[str, Any]) -> None:
    """Validate *data* against the official OSI core JSON Schema."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:  # pragma: no cover - dependency packaging guard
        raise OSIValidationError(
            "jsonschema is required to validate OSI core schema documents."
        ) from e

    validator = Draft202012Validator(osi_core_schema())
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if not errors:
        return
    first = errors[0]
    raise OSIValidationError(
        "OSI core schema validation failed at "
        f"{_json_schema_path(first.path)}: {first.message}"
    )


def _looks_like_core_document(data: Dict[str, Any]) -> bool:
    return "version" in data or isinstance(data.get("semantic_model"), list)


def _single_relationship_column(value: Any, field_name: str, rel_name: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    name = f" `{rel_name}`" if rel_name else ""
    raise ValueError(
        f"Relationship{name} uses `{field_name}`={value!r}; the current Datus "
        "execution profile supports OSI relationships with exactly one column "
        "on each side."
    )


def _datus_hints(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and parse Datus hints from an object's ``custom_extensions``.

    OSI core carries vendor-specific data under ``custom_extensions`` entries
    whose ``vendor_name`` is ``DATUS`` and whose ``data`` is a JSON string.
    """
    hints: Dict[str, Any] = {}
    for ext in obj.get("custom_extensions") or []:
        if not isinstance(ext, dict):
            continue
        if str(ext.get("vendor_name", "")).upper() != DATUS_VENDOR:
            continue
        raw = ext.get("data")
        if isinstance(raw, dict):
            _reject_filter_hints(raw)
            hints.update(raw)
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                raise OSIValidationError(
                    "DATUS custom extension data must be a valid JSON string."
                ) from e
            if not isinstance(parsed, dict):
                raise OSIValidationError(
                    "DATUS custom extension data must decode to a JSON object."
                )
            _reject_filter_hints(parsed)
            hints.update(parsed)
    return hints


def _reject_filter_hints(value: Any, path: str = "DATUS custom extension") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}"
            if str(key).lower() in _DISALLOWED_DATUS_HINT_KEYS:
                raise OSIValidationError(
                    f"{next_path} is not an OSI authoring field. Encode fixed "
                    "dataset scope in the dataset source/description/ai_context, "
                    "and encode metric-specific conditional semantics inside the "
                    "metric expression."
                )
            _reject_filter_hints(item, next_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_filter_hints(item, f"{path}[{index}]")


def _validate_datus_hint_keys(
    hints: Dict[str, Any],
    allowed: set[str],
    object_type: str,
    object_name: Optional[str],
) -> None:
    unknown = sorted(str(key) for key in hints if key not in allowed)
    if not unknown:
        return
    name = f" `{object_name}`" if object_name else ""
    raise OSIValidationError(
        f"{object_type}{name} declares unsupported DATUS custom extension key(s) "
        f"{unknown}. Use only OSI core fields plus supported DATUS execution hints."
    )


def _metric_metadata_from_hints(
    hints: Dict[str, Any], metric_name: Optional[str]
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    raw_metadata = hints.get("metadata")
    if raw_metadata is not None:
        if not isinstance(raw_metadata, dict):
            name = f" `{metric_name}`" if metric_name else ""
            raise OSIValidationError(
                f"Metric{name} DATUS `metadata` hint must be a JSON object."
            )
        _validate_datus_hint_keys(
            raw_metadata,
            _METRIC_METADATA_HINT_KEYS,
            "Metric metadata",
            metric_name,
        )
        metadata.update(raw_metadata)
    for key in _METRIC_METADATA_HINT_KEYS:
        if key in hints:
            metadata[key] = hints[key]
    return metadata


def _merge_datus_extensions(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *obj* with DATUS custom_extensions hints merged in.

    Inline keys take precedence over hint keys; ``custom_extensions`` is dropped.
    """
    if not isinstance(obj, dict):
        return obj
    hints = _datus_hints(obj)
    merged = {k: v for k, v in obj.items() if k != "custom_extensions"}
    for key, value in hints.items():
        merged.setdefault(key, value)
    if "name" in merged and (
        "expression" in merged or "metric_kind" in merged or "metric_type" in merged
    ):
        metric_fields = set(OSIMetric.model_fields)
        metadata = dict(merged.get("metadata") or {})
        for key in list(merged):
            if key in metric_fields:
                continue
            if key in {"name", "description", "expression"}:
                continue
            metadata[key] = merged.pop(key)
        if metadata:
            merged["metadata"] = metadata
    return merged


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _datus_extension(hints: Dict[str, Any]) -> List[Dict[str, str]]:
    clean = {
        key: _jsonable(value)
        for key, value in hints.items()
        if value not in (None, "", [], {})
    }
    if not clean:
        return []
    return [
        {
            "vendor_name": DATUS_VENDOR,
            "data": json.dumps(clean, ensure_ascii=False, sort_keys=True),
        }
    ]


def _core_expression(expression: Optional[str]) -> Dict[str, Any]:
    return {
        "dialects": [
            {
                "dialect": DEFAULT_DIALECT,
                "expression": expression or "1",
            }
        ]
    }


def _first_core_expression(obj: Dict[str, Any]) -> str:
    expression = obj.get("expression")
    if isinstance(expression, str):
        return expression
    if not isinstance(expression, dict):
        return ""
    dialects = expression.get("dialects") or []
    for item in dialects:
        if isinstance(item, dict) and item.get("dialect") == DEFAULT_DIALECT:
            return str(item.get("expression") or "")
    for item in dialects:
        if isinstance(item, dict) and item.get("expression"):
            return str(item["expression"])
    return ""


def _source_from_core(dataset: Dict[str, Any], hints: Dict[str, Any]) -> Dict[str, str]:
    source_hint = hints.get("source")
    if isinstance(source_hint, dict):
        if source_hint.get("query"):
            return {"query": str(source_hint["query"])}
        if source_hint.get("table"):
            return {"table": str(source_hint["table"])}

    source = str(dataset.get("source") or "")
    source_type = str(hints.get("source_type") or "").lower()
    starts_like_query = source.lstrip().lower().startswith(("select ", "with ", "("))
    if source_type == "query" or starts_like_query:
        return {"query": source}
    return {"table": source}


def _time_dimension_from_hint(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, str) and value:
        return {"name": value, "granularity": "day"}
    if isinstance(value, dict) and value.get("name"):
        result = {
            "name": value["name"],
            "granularity": value.get("granularity")
            or value.get("time_granularity")
            or "day",
        }
        if value.get("expr"):
            result["expr"] = value["expr"]
        return result
    return None


def _core_dataset_to_profile(dataset: Dict[str, Any]) -> Dict[str, Any]:
    hints = _datus_hints(dataset)
    _validate_datus_hint_keys(
        hints, _DATASET_DATUS_HINT_KEYS, "Dataset", dataset.get("name")
    )
    fields = [field for field in dataset.get("fields") or [] if isinstance(field, dict)]
    profile: Dict[str, Any] = {
        "name": dataset["name"],
        "source": _source_from_core(dataset, hints),
    }
    if dataset.get("description"):
        profile["description"] = dataset["description"]
    if dataset.get("ai_context"):
        profile["ai_context"] = dataset["ai_context"]
    if dataset.get("primary_key"):
        keys = list(dataset["primary_key"])
        profile["primary_key"] = keys[0] if len(keys) == 1 else keys

    explicit_time_dimension = _time_dimension_from_hint(hints.get("time_dimension"))
    primary_time_field = None
    if explicit_time_dimension:
        primary_time_field = str(explicit_time_dimension["name"])
        profile["time_dimension"] = explicit_time_dimension

    dimensions: List[Dict[str, Any]] = []
    for field in fields:
        field_hints = _datus_hints(field)
        name = field.get("name")
        _validate_datus_hint_keys(
            field_hints, _FIELD_DATUS_HINT_KEYS, "Field", str(name) if name else None
        )
        if not name:
            continue
        is_time = bool((field.get("dimension") or {}).get("is_time"))
        expr = _first_core_expression(field) or str(name)
        granularity = field_hints.get("time_granularity") or field_hints.get(
            "granularity"
        )

        if is_time and primary_time_field is None:
            primary_time_field = str(name)
            profile["time_dimension"] = {
                "name": str(name),
                "expr": expr,
                "granularity": granularity or "day",
            }
            if field.get("ai_context"):
                profile["time_dimension"]["ai_context"] = field["ai_context"]
            continue
        if str(name) == primary_time_field:
            time_dimension = profile.get("time_dimension")
            if isinstance(time_dimension, dict):
                time_dimension.setdefault("expr", expr)
                if granularity:
                    time_dimension.setdefault("granularity", granularity)
                if field.get("ai_context"):
                    time_dimension.setdefault("ai_context", field["ai_context"])
            continue

        dim_type = field_hints.get("type") or ("time" if is_time else "categorical")
        dim: Dict[str, Any] = {
            "name": str(name),
            "expr": expr,
            "type": dim_type,
        }
        if field.get("description"):
            dim["description"] = field["description"]
        if field.get("ai_context"):
            dim["ai_context"] = field["ai_context"]
        if granularity:
            dim["granularity"] = granularity
        dimensions.append(dim)

    if dimensions:
        profile["dimensions"] = dimensions
    return profile


def _core_metric_to_profile(
    metric: Dict[str, Any], default_dataset: Optional[str]
) -> Dict[str, Any]:
    hints = _datus_hints(metric)
    _validate_datus_hint_keys(
        hints, _METRIC_DATUS_HINT_KEYS, "Metric", metric.get("name")
    )
    profile = {
        "name": metric["name"],
        "description": metric.get("description") or "",
        "expression": _first_core_expression(metric),
    }
    if metric.get("ai_context") not in (None, "", [], {}):
        profile["ai_context"] = metric["ai_context"]
    for key in (
        "metric_kind",
        "metric_type",
        "numerator",
        "denominator",
        "inputs",
        "dataset",
        "time_dimension",
        "window",
        "grain_to_date",
        "offset_window",
        "subject_path",
        "format",
        "unit",
        "non_additive_dimension",
        "period_over_period",
    ):
        if key in hints:
            profile[key] = hints[key]
    metadata = _metric_metadata_from_hints(hints, metric.get("name"))
    if metadata:
        profile["metadata"] = metadata
    kind = str(profile.get("metric_kind") or profile.get("metric_type") or "").lower()
    if not profile.get("dataset") and default_dataset and kind != "derived":
        profile["dataset"] = default_dataset
    return profile


def _core_relationship_to_profile(relationship: Dict[str, Any]) -> Dict[str, Any]:
    hints = _datus_hints(relationship)
    _validate_datus_hint_keys(
        hints, _RELATIONSHIP_DATUS_HINT_KEYS, "Relationship", relationship.get("name")
    )
    profile = {
        "name": relationship["name"],
        "from": relationship["from"],
        "to": relationship["to"],
        "from_columns": relationship["from_columns"],
        "to_columns": relationship["to_columns"],
    }
    if hints.get("type"):
        profile["type"] = hints["type"]
    return profile


def _core_model_to_profile(model: Dict[str, Any]) -> OSIDocument:
    datasets = [_core_dataset_to_profile(ds) for ds in model.get("datasets") or []]
    default_dataset = datasets[0]["name"] if len(datasets) == 1 else None
    return OSIDocument(
        name=model.get("name") or "datus_semantic_model",
        datasets=datasets,
        relationships=[
            _core_relationship_to_profile(rel)
            for rel in model.get("relationships") or []
            if isinstance(rel, dict)
        ],
        metrics=[
            _core_metric_to_profile(metric, default_dataset)
            for metric in model.get("metrics") or []
            if isinstance(metric, dict)
        ],
    )


def load_osi_path(
    path: str,
    normalize: bool = False,
    *,
    allow_legacy_profile: bool = False,
) -> OSIDocument:
    """Load a strict OSI core document from a YAML file or directory.

    The public authoring contract is the official OSI core schema. Legacy Datus
    profile documents are accepted only when ``allow_legacy_profile`` is set,
    which is intended for migration / internal compatibility code.
    """
    import glob as _glob
    import os as _os

    if _os.path.isdir(path):
        files = sorted(
            _glob.glob(_os.path.join(path, "**", "*.yaml"), recursive=True)
            + _glob.glob(_os.path.join(path, "**", "*.yml"), recursive=True)
        )
    else:
        files = [path]
    core_docs: List[Dict[str, Any]] = []
    legacy_docs: List[Dict[str, Any]] = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            docs = list(yaml.safe_load_all(fh.read())) or []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if _looks_like_core_document(doc):
                core_docs.append(doc)
            else:
                legacy_docs.append(doc)

    if legacy_docs and not allow_legacy_profile:
        raise OSIValidationError(
            "OSI authoring files must conform to OSI core schema "
            f"(version: {CORE_SCHEMA_VERSION}, semantic_model: [...]). "
            "Legacy Datus profile YAML with top-level datasets/metrics is not accepted."
        )
    if core_docs and legacy_docs:
        raise OSIValidationError(
            "Cannot mix strict OSI core documents with legacy Datus profile documents "
            "in the same semantic model directory."
        )
    if legacy_docs:
        doc = parse_osi_profile(_merge_legacy_profile_documents(legacy_docs))
    elif core_docs:
        doc = parse_osi(_merge_core_documents(core_docs))
    else:
        raise OSIValidationError(f"No OSI YAML documents found under {path}.")

    if normalize:
        from datus_semantic_osi.normalizer import normalize_document

        result = normalize_document(doc)
        if result.errors:
            raise OSIValidationError(" ".join(result.errors))
        return result.document
    return doc


def _merge_legacy_profile_documents(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "semantic_model": {},
        "datasets": [],
        "relationships": [],
        "metrics": [],
    }
    for doc in docs:
        if doc.get("semantic_model"):
            merged["semantic_model"] = doc["semantic_model"]
        merged["datasets"].extend(doc.get("datasets", []))
        merged["relationships"].extend(doc.get("relationships", []))
        merged["metrics"].extend(doc.get("metrics", []))
        metric = doc.get("metric")
        if isinstance(metric, dict):
            merged["metrics"].append(metric)
    merged["datasets"] = _dedupe_datasets(merged["datasets"])
    return merged


def _dedupe_exact(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fingerprints = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        fingerprint = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        result.append(item)
    return result


def _merge_core_documents(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    model_name: Optional[str] = None
    merged_model: Dict[str, Any] = {
        "name": "",
        "datasets": [],
        "relationships": [],
        "metrics": [],
    }
    for doc in docs:
        validate_osi_core_schema(doc)
        if doc.get("version") != CORE_SCHEMA_VERSION:
            raise OSIValidationError(
                f"Unsupported OSI core schema version `{doc.get('version')}`; "
                f"expected `{CORE_SCHEMA_VERSION}`."
            )
        for model in doc.get("semantic_model") or []:
            name = str(model.get("name") or "")
            if model_name is None:
                model_name = name
                merged_model["name"] = name
                if model.get("description"):
                    merged_model["description"] = model["description"]
            elif name != model_name:
                raise OSIValidationError(
                    "Datus OSI currently executes one semantic model per datasource; "
                    f"found both `{model_name}` and `{name}`."
                )
            merged_model["datasets"].extend(model.get("datasets") or [])
            merged_model["relationships"].extend(model.get("relationships") or [])
            merged_model["metrics"].extend(model.get("metrics") or [])

    merged_model["datasets"] = _dedupe_datasets(merged_model["datasets"])
    merged_model["relationships"] = _dedupe_exact(merged_model["relationships"])
    return {
        "version": CORE_SCHEMA_VERSION,
        "semantic_model": [merged_model],
    }


def _dedupe_datasets(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicate dataset declarations that are byte-for-byte identical.

    Across files the same dataset is often re-declared identically; merging those
    is safe. Same-name-but-different-definition is left as-is so the validator can
    flag it (rename / reconcile is then the author's call).
    """
    import json as _json

    seen: Dict[str, str] = {}
    result: List[Dict[str, Any]] = []
    for ds in datasets:
        name = ds.get("name") if isinstance(ds, dict) else None
        if name is None:
            result.append(ds)
            continue
        fingerprint = _json.dumps(ds, sort_keys=True, ensure_ascii=False, default=str)
        if name in seen:
            if seen[name] == fingerprint:
                continue  # identical re-declaration -> drop the duplicate
            result.append(ds)  # genuine conflict -> keep both; validator reports it
        else:
            seen[name] = fingerprint
            result.append(ds)
    return result


def parse_osi(
    data: Union[str, dict],
    *,
    allow_legacy_profile: bool = False,
) -> OSIDocument:
    """Parse strict OSI core YAML (or an already-loaded dict) into OSIDocument."""
    if isinstance(data, str):
        data = yaml.safe_load(data)
    if not isinstance(data, dict):
        raise ValueError("OSI document must be a mapping")
    if not _looks_like_core_document(data):
        if allow_legacy_profile:
            return parse_osi_profile(data)
        raise OSIValidationError(
            "OSI document must conform to OSI core schema: root keys must be "
            f"`version: {CORE_SCHEMA_VERSION}` and `semantic_model: [...]`."
        )
    validate_osi_core_schema(data)
    models = data.get("semantic_model") or []
    if len(models) != 1:
        raise OSIValidationError(
            "Datus OSI currently supports exactly one OSI core semantic_model per "
            f"executable document; found {len(models)}."
        )
    return _core_model_to_profile(models[0])


def parse_osi_profile(data: Union[str, dict]) -> OSIDocument:
    """Parse the legacy Datus executable profile shape.

    This is intentionally not the public authoring contract; use it only for
    migration or tests that exercise internal compiler behavior.
    """
    if isinstance(data, str):
        data = yaml.safe_load(data)
    if not isinstance(data, dict):
        raise ValueError("OSI profile document must be a mapping")
    semantic_model = data.get("semantic_model") or {}
    return OSIDocument(
        name=semantic_model.get("name", "datus_semantic_model"),
        datasets=[_merge_datus_extensions(d) for d in data.get("datasets", [])],
        relationships=data.get("relationships", []),
        metrics=[_merge_datus_extensions(m) for m in data.get("metrics", [])],
    )


def to_core_schema_document(doc: OSIDocument) -> Dict[str, Any]:
    """Serialize an internal OSIDocument as strict OSI core schema."""
    model: Dict[str, Any] = {
        "name": doc.name,
        "datasets": [],
    }
    if doc.relationships:
        model["relationships"] = []
    if doc.metrics:
        model["metrics"] = []

    for dataset in doc.datasets:
        source = dataset.source.table or dataset.source.query or dataset.name
        dataset_hints: Dict[str, Any] = {}
        if dataset.source.query and not dataset.source.table:
            dataset_hints["source_type"] = "query"
        if dataset.time_dimension:
            dataset_hints["time_dimension"] = dataset.time_dimension

        core_dataset: Dict[str, Any] = {
            "name": dataset.name,
            "source": source,
        }
        if dataset.description:
            core_dataset["description"] = dataset.description
        if dataset.ai_context:
            core_dataset["ai_context"] = dataset.ai_context
        if dataset.primary_key:
            keys = (
                [dataset.primary_key]
                if isinstance(dataset.primary_key, str)
                else list(dataset.primary_key)
            )
            core_dataset["primary_key"] = keys

        fields: List[Dict[str, Any]] = []
        if dataset.time_dimension:
            time_hints = {
                "type": "time",
                "time_granularity": dataset.time_dimension.granularity,
            }
            fields.append(
                {
                    "name": dataset.time_dimension.name,
                    "expression": _core_expression(
                        dataset.time_dimension.expr or dataset.time_dimension.name
                    ),
                    "dimension": {"is_time": True},
                    "custom_extensions": _datus_extension(time_hints),
                    **(
                        {"ai_context": dataset.time_dimension.ai_context}
                        if dataset.time_dimension.ai_context
                        else {}
                    ),
                }
            )
        for dim in dataset.dimensions:
            field: Dict[str, Any] = {
                "name": dim.name,
                "expression": _core_expression(dim.expr or dim.name),
                "dimension": {"is_time": dim.type == "time"},
            }
            if dim.description:
                field["description"] = dim.description
            if dim.ai_context:
                field["ai_context"] = dim.ai_context
            hints = {"type": dim.type, "time_granularity": dim.granularity}
            ext = _datus_extension(hints)
            if ext:
                field["custom_extensions"] = ext
            fields.append(field)
        if fields:
            core_dataset["fields"] = fields
        ext = _datus_extension(dataset_hints)
        if ext:
            core_dataset["custom_extensions"] = ext
        model["datasets"].append(core_dataset)

    for rel in doc.relationships:
        core_rel: Dict[str, Any] = {
            "name": rel.name,
            "from": rel.from_dataset,
            "to": rel.to_dataset,
            "from_columns": [rel.from_identifier],
            "to_columns": [rel.to_identifier],
        }
        if rel.ai_context:
            core_rel["ai_context"] = rel.ai_context
        ext = _datus_extension(
            {"type": rel.type if rel.type != "many_to_one" else None}
        )
        if ext:
            core_rel["custom_extensions"] = ext
        model.setdefault("relationships", []).append(core_rel)

    for metric in doc.metrics:
        metric_hints = {
            "metric_kind": metric.metric_kind,
            "metric_type": metric.metric_type,
            "numerator": metric.numerator,
            "denominator": metric.denominator,
            "inputs": metric.inputs,
            "dataset": metric.dataset,
            "time_dimension": metric.time_dimension,
            "window": metric.window,
            "grain_to_date": metric.grain_to_date,
            "offset_window": metric.offset_window,
            "subject_path": metric.subject_path,
            "format": metric.format,
            "unit": metric.unit,
            "non_additive_dimension": metric.non_additive_dimension,
            "period_over_period": metric.period_over_period,
        }
        for key, value in metric.metadata.items():
            metric_hints.setdefault(key, value)
        expression = metric.expression
        if not expression and metric.numerator and metric.denominator:
            expression = f"{metric.numerator} / {metric.denominator}"
        if not expression and metric.inputs:
            expression = " + ".join(
                str(item.name if isinstance(item, OSIMetricInput) else item)
                for item in metric.inputs
            )
        core_metric: Dict[str, Any] = {
            "name": metric.name,
            "expression": _core_expression(expression),
        }
        if metric.description:
            core_metric["description"] = metric.description
        if metric.ai_context:
            core_metric["ai_context"] = metric.ai_context
        ext = _datus_extension(metric_hints)
        if ext:
            core_metric["custom_extensions"] = ext
        model.setdefault("metrics", []).append(core_metric)

    return {
        "version": CORE_SCHEMA_VERSION,
        "semantic_model": [model],
    }

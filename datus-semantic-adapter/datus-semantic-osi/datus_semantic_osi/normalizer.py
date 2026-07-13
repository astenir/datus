# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Conservative normalization for OSI authoring documents.

The normalizer treats datasets as logical datasets. It only collapses duplicate
physical-table aliases when they have no logical distinction: same source table,
and no source query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from datus_semantic_osi.profile import (
    OSIDataset,
    OSIDimension,
    OSIDocument,
    OSITimeDimension,
)


@dataclass
class NormalizationResult:
    """The result of applying safe OSI document normalization."""

    document: OSIDocument
    actions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dataset_aliases: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _FieldSig:
    name: str
    expr: str
    type: str
    granularity: Optional[str] = None


_CATEGORICAL_TYPES = {"categorical", "string", "str", "text", "varchar", "char"}
_NUMERIC_TYPES = {"numeric", "number", "int", "integer", "bigint", "float", "double", "decimal"}


def _norm_identifier(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().strip("`\"'[]").lower())


def _norm_table(table: Optional[str]) -> str:
    if not table:
        return ""
    parts = [_norm_identifier(part) for part in str(table).split(".")]
    return ".".join(part for part in parts if part)


def _table_leaf(table: Optional[str]) -> str:
    normalized = _norm_table(table)
    return normalized.split(".")[-1] if normalized else ""


def _norm_type(value: Optional[str]) -> str:
    raw = _norm_identifier(value or "categorical")
    if raw in _CATEGORICAL_TYPES:
        return "categorical"
    if raw in _NUMERIC_TYPES:
        return "numeric"
    if raw == "time":
        return "time"
    return raw


def _pk_tuple(value: object) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(_norm_identifier(v) for v in value)
    return (_norm_identifier(value),)


def _time_sig(td: OSITimeDimension) -> _FieldSig:
    return _FieldSig(
        name=_norm_identifier(td.name),
        expr=_norm_identifier(td.name),
        type="time",
        granularity=_norm_identifier(td.granularity or "day"),
    )


def _dimension_sig(dim: OSIDimension) -> _FieldSig:
    return _FieldSig(
        name=_norm_identifier(dim.name),
        expr=_norm_identifier(dim.expr or dim.name),
        type=_norm_type(dim.type),
        granularity=_norm_identifier(dim.granularity) if dim.granularity else None,
    )


def _field_conflict(existing: _FieldSig, incoming: _FieldSig) -> Optional[str]:
    if existing.expr and incoming.expr and existing.expr != incoming.expr:
        return f"field `{incoming.name}` maps to both `{existing.expr}` and `{incoming.expr}`"
    if existing.type != incoming.type:
        return f"field `{incoming.name}` is both `{existing.type}` and `{incoming.type}`"
    if (
        existing.granularity
        and incoming.granularity
        and existing.granularity != incoming.granularity
    ):
        return (
            f"time field `{incoming.name}` uses both `{existing.granularity}` "
            f"and `{incoming.granularity}` granularity"
        )
    return None


def _dataset_score(index: int, ds: OSIDataset) -> Tuple[int, int, int, int, int]:
    table = ds.source.table
    name = _norm_identifier(ds.name)
    exact_name = int(name in {_norm_table(table), _table_leaf(table)})
    return (
        exact_name,
        int(ds.time_dimension is not None),
        int(bool(ds.primary_key)),
        len(ds.dimensions),
        -index,
    )


def _eligible_table_groups(doc: OSIDocument) -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {}
    for idx, ds in enumerate(doc.datasets):
        table_key = _norm_table(ds.source.table)
        if not table_key:
            continue
        if ds.source.query:
            continue
        groups.setdefault(table_key, []).append(idx)
    return {table: indexes for table, indexes in groups.items() if len(indexes) > 1}


def _merge_into(canonical: OSIDataset, duplicate: OSIDataset) -> List[str]:
    errors: List[str] = []
    canonical_pk = _pk_tuple(canonical.primary_key)
    duplicate_pk = _pk_tuple(duplicate.primary_key)
    if canonical_pk and duplicate_pk and canonical_pk != duplicate_pk:
        errors.append(
            f"Dataset `{duplicate.name}` duplicates table `{duplicate.source.table}` "
            f"but primary key conflicts with `{canonical.name}`."
        )

    if canonical.time_dimension and duplicate.time_dimension:
        current = _time_sig(canonical.time_dimension)
        incoming = _time_sig(duplicate.time_dimension)
        conflict = _field_conflict(current, incoming)
        if current.name != incoming.name or conflict:
            errors.append(
                f"Dataset `{duplicate.name}` duplicates table `{duplicate.source.table}` "
                f"but time dimension conflicts with `{canonical.name}`."
            )

    existing_fields: Dict[str, _FieldSig] = {}
    if canonical.time_dimension:
        sig = _time_sig(canonical.time_dimension)
        existing_fields[sig.name] = sig
    for dim in canonical.dimensions:
        sig = _dimension_sig(dim)
        existing_fields[sig.name] = sig

    if duplicate.time_dimension:
        incoming_time = _time_sig(duplicate.time_dimension)
        existing = existing_fields.get(incoming_time.name)
        if existing:
            conflict = _field_conflict(existing, incoming_time)
            if conflict:
                errors.append(
                    f"Dataset `{duplicate.name}` duplicates table `{duplicate.source.table}` "
                    f"but {conflict}."
                )
        elif canonical.time_dimension is None:
            canonical.time_dimension = duplicate.time_dimension.model_copy(deep=True)
            existing_fields[incoming_time.name] = incoming_time

    for dim in duplicate.dimensions:
        incoming = _dimension_sig(dim)
        existing = existing_fields.get(incoming.name)
        if existing:
            conflict = _field_conflict(existing, incoming)
            if conflict:
                errors.append(
                    f"Dataset `{duplicate.name}` duplicates table `{duplicate.source.table}` "
                    f"but {conflict}."
                )
            continue
        canonical.dimensions.append(dim.model_copy(deep=True))
        existing_fields[incoming.name] = incoming

    if canonical.primary_key is None and duplicate.primary_key is not None:
        canonical.primary_key = duplicate.primary_key

    return errors


def _rewrite_relationships(doc: OSIDocument, aliases: Dict[str, str], actions: List[str]) -> None:
    rewritten = []
    seen = set()
    for rel in doc.relationships:
        old_from = rel.from_dataset
        old_to = rel.to_dataset
        rel.from_dataset = aliases.get(rel.from_dataset, rel.from_dataset)
        rel.to_dataset = aliases.get(rel.to_dataset, rel.to_dataset)
        if rel.from_dataset == rel.to_dataset:
            actions.append(
                f"Dropped relationship `{rel.name}` after dataset normalization made it self-referential."
            )
            continue
        key = (
            rel.name,
            rel.type,
            rel.from_dataset,
            rel.from_identifier,
            rel.to_dataset,
            rel.to_identifier,
        )
        if key in seen:
            actions.append(f"Dropped duplicate relationship `{rel.name}` after dataset normalization.")
            continue
        seen.add(key)
        if old_from != rel.from_dataset or old_to != rel.to_dataset:
            actions.append(
                f"Rewrote relationship `{rel.name}` from `{old_from}->{old_to}` "
                f"to `{rel.from_dataset}->{rel.to_dataset}`."
            )
        rewritten.append(rel)
    doc.relationships = rewritten


def _rewrite_metrics(doc: OSIDocument, aliases: Dict[str, str], actions: List[str]) -> None:
    for metric in doc.metrics:
        if metric.dataset in aliases:
            old = metric.dataset
            metric.dataset = aliases[old]
            actions.append(
                f"Rewrote metric `{metric.name}` dataset from `{old}` to `{metric.dataset}`."
            )


def normalize_document(doc: OSIDocument) -> NormalizationResult:
    """Return a conservatively normalized copy of *doc*.

    Only duplicate physical-table aliases with no source query are collapsed.
    Ambiguous duplicates are reported as errors and left unchanged.
    """

    normalized = doc.model_copy(deep=True)
    result = NormalizationResult(document=normalized)
    groups = _eligible_table_groups(normalized)
    remove_indexes: set[int] = set()
    canonical_updates: Dict[int, OSIDataset] = {}

    for table, indexes in groups.items():
        canonical_idx = max(indexes, key=lambda i: _dataset_score(i, normalized.datasets[i]))
        candidate = normalized.datasets[canonical_idx].model_copy(deep=True)
        group_errors: List[str] = []
        group_aliases: Dict[str, str] = {}

        for idx in indexes:
            if idx == canonical_idx:
                continue
            duplicate = normalized.datasets[idx]
            errors = _merge_into(candidate, duplicate)
            if errors:
                group_errors.extend(errors)
                continue
            group_aliases[duplicate.name] = candidate.name

        if group_errors:
            result.errors.extend(group_errors)
            continue

        canonical_updates[canonical_idx] = candidate
        result.dataset_aliases.update(group_aliases)
        remove_indexes.update(idx for idx in indexes if idx != canonical_idx)
        for duplicate, canonical in group_aliases.items():
            result.actions.append(
                f"Collapsed duplicate dataset `{duplicate}` into canonical dataset `{canonical}` "
                f"for table `{table}`."
            )

    for idx, ds in canonical_updates.items():
        normalized.datasets[idx] = ds

    if result.dataset_aliases:
        _rewrite_metrics(normalized, result.dataset_aliases, result.actions)
        _rewrite_relationships(normalized, result.dataset_aliases, result.actions)
        normalized.datasets = [
            ds for idx, ds in enumerate(normalized.datasets) if idx not in remove_indexes
        ]
        result.warnings.append(
            "Normalized duplicate physical-table dataset aliases to canonical dataset names."
        )

    return result


def normalization_errors(doc: OSIDocument) -> List[str]:
    """Return unsafe duplicate-table dataset issues without using the normalized doc."""

    return normalize_document(doc).errors

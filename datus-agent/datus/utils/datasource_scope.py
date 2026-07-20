"""Helpers for evaluating datasource catalog-tree grant scopes."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Mapping, Sequence

_SCOPE_KEYS = {
    "catalog": "catalogs",
    "database": "databases",
    "schema": "schemas",
    "table": "tables",
}
SCOPE_CONSTRAINTS_KEY = "_scope_constraints"


def datasource_field_order(datasource_type: str) -> list[str]:
    """Return the catalog coordinate fields supported by a datasource dialect."""

    from datus_db_core import connector_registry

    dialect = datasource_type.strip().lower()
    fields: list[str] = []
    if connector_registry.support_catalog(dialect):
        fields.append("catalog")
    if connector_registry.support_database(dialect) or dialect == "sqlite":
        fields.append("database")
    if connector_registry.support_schema(dialect) or dialect in {"postgres", "postgresql", "greenplum", "redshift"}:
        fields.append("schema")
    fields.append("table")
    return fields


def datasource_scope_matches(
    grant: Mapping[str, Any],
    *,
    coordinate: Mapping[str, str],
    target_field: str,
    field_order: Sequence[str],
    include_descendants: bool = True,
) -> bool:
    """Evaluate a datasource scope at one catalog-tree coordinate.

    Namespace discovery normally includes ancestors of selected descendants.
    Callers can disable that behavior when they need to distinguish an explicit
    namespace grant from visibility derived only from a table leaf.
    """

    if str(grant.get("effect", "allow")).strip().lower() != "allow":
        return False
    constraints = grant.get(SCOPE_CONSTRAINTS_KEY)
    if isinstance(constraints, (list, tuple)) and constraints:
        return all(
            isinstance(constraint, Mapping)
            and datasource_scope_matches(
                constraint,
                coordinate=coordinate,
                target_field=target_field,
                field_order=field_order,
                include_descendants=include_descendants,
            )
            for constraint in constraints
        )
    if grant_uses_tree_scope(grant, field_order):
        return tree_scope_matches(
            grant,
            coordinate=coordinate,
            target_field=target_field,
            field_order=field_order,
            include_descendants=include_descendants,
        )
    return _legacy_scope_matches(
        grant,
        coordinate=coordinate,
        target_field=target_field,
        field_order=field_order,
    )


def grant_uses_tree_scope(grant: Mapping[str, Any], field_order: Sequence[str]) -> bool:
    """Return whether qualified leaf/namespace entries represent selected tree nodes.

    Legacy hand-written grants often combine unqualified dimension filters, for
    example ``schemas=["public"]`` plus ``tables=["*"]``. Those remain
    conjunctive. The role editor, however, stores selected leaves as complete
    paths such as ``database.schema.table``; sibling database/schema/table
    selections in that shape are independent branches and must be unioned.
    """

    table_patterns = grant_scope_patterns(grant, "tables")
    if table_patterns:
        return all(_complete_scope_pattern(pattern, "table", field_order) for pattern in table_patterns)

    schema_patterns = grant_scope_patterns(grant, "schemas")
    if schema_patterns:
        return all(_complete_scope_pattern(pattern, "schema", field_order) for pattern in schema_patterns)

    return False


def tree_scope_matches(
    grant: Mapping[str, Any],
    *,
    coordinate: Mapping[str, str],
    target_field: str,
    field_order: Sequence[str],
    include_descendants: bool = True,
) -> bool:
    """Match a coordinate against the union of selected catalog-tree nodes.

    A selected ancestor authorizes its descendants. A selected descendant keeps
    its ancestors visible unless ``include_descendants`` is false.
    """

    if target_field not in field_order:
        return False
    target_index = field_order.index(target_field)

    for selected_field, scope_key in _SCOPE_KEYS.items():
        if selected_field not in field_order:
            continue
        selected_index = field_order.index(selected_field)
        if not include_descendants and selected_index > target_index:
            continue
        for raw_pattern in grant_scope_patterns(grant, scope_key) or []:
            pattern = _parse_scope_pattern(raw_pattern, selected_field, field_order)
            if pattern is None or any(not pattern.get(field) for field in field_order[: selected_index + 1]):
                continue
            common_fields = field_order[: min(target_index, selected_index) + 1]
            if all(_pattern_matches(pattern[field], coordinate.get(field, ""), field=field) for field in common_fields):
                return True
    return False


def grant_scope_patterns(grant: Mapping[str, Any], scope_key: str) -> list[str] | None:
    """Normalize one grant scope field while preserving legacy empty-as-unset behavior."""

    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    patterns = [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]
    return patterns or None


def grant_may_use_tree_scope(grant: Mapping[str, Any]) -> bool:
    """Conservatively detect qualified tree scopes before a dialect is available."""

    table_patterns = grant_scope_patterns(grant, "tables")
    if table_patterns:
        return all(len(_pattern_parts(pattern)) >= 3 for pattern in table_patterns)
    schema_patterns = grant_scope_patterns(grant, "schemas")
    return bool(schema_patterns) and all(len(_pattern_parts(pattern)) >= 2 for pattern in schema_patterns)


def _complete_scope_pattern(pattern: str, target_field: str, field_order: Sequence[str]) -> bool:
    parsed = _parse_scope_pattern(pattern, target_field, field_order)
    if parsed is None:
        return False
    prefix = field_order[: field_order.index(target_field) + 1]
    return all(parsed.get(field) for field in prefix)


def _parse_scope_pattern(
    pattern: str,
    target_field: str,
    field_order: Sequence[str],
) -> dict[str, str] | None:
    if target_field not in field_order:
        return None
    fields = list(field_order[: field_order.index(target_field) + 1])
    parts = _pattern_parts(pattern)
    if not parts or len(parts) > len(fields):
        return None
    values = {field: "" for field in fields}
    for field, part in zip(reversed(fields), reversed(parts)):
        values[field] = part
    return values


def _legacy_scope_matches(
    grant: Mapping[str, Any],
    *,
    coordinate: Mapping[str, str],
    target_field: str,
    field_order: Sequence[str],
) -> bool:
    if target_field not in field_order:
        return False
    for field in field_order[: field_order.index(target_field) + 1]:
        patterns = grant_scope_patterns(grant, _SCOPE_KEYS[field])
        if patterns is None:
            continue
        if not any(
            (parsed := _parse_scope_pattern(raw_pattern, field, field_order)) is not None
            and all(
                not pattern or _pattern_matches(pattern, coordinate.get(candidate_field, ""), field=candidate_field)
                for candidate_field, pattern in parsed.items()
            )
            for raw_pattern in patterns
        ):
            return False
    return True


def _pattern_parts(pattern: str) -> list[str]:
    return [part.strip() for part in str(pattern).split(".") if part.strip()]


def _pattern_matches(pattern: str, value: str, *, field: str) -> bool:
    if not pattern or pattern in ("*", "%"):
        return True
    if not value:
        return field == "catalog"
    return fnmatchcase(value, pattern.replace("%", "*"))

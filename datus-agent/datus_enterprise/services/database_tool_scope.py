"""Datasource-grant scope policy for the downstream database tool."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Mapping, Sequence

from datus.utils.datasource_scope import datasource_scope_matches, grant_uses_tree_scope


class DatabaseToolScopePolicy:
    """Evaluate projected datasource grants without owning DB tool execution."""

    def __init__(
        self,
        principal: Mapping[str, Any],
        default_datasource: str,
        field_order: Sequence[str],
    ) -> None:
        self._principal = principal
        self._default_datasource = default_datasource
        self._field_order = tuple(field_order)

    def scope_matches(self, scope_key: str, candidates: Sequence[str], datasource: str = "") -> bool:
        grant = self.datasource_grant(datasource)
        if grant is None or grant is True:
            return True
        if not isinstance(grant, Mapping) or not _is_allow_grant(grant):
            return False

        patterns = _scope_patterns(grant, scope_key)
        if patterns is None:
            return True
        values = [str(candidate).strip() for candidate in candidates if str(candidate).strip()]
        if not patterns:
            return False
        if not values:
            return any(pattern in ("*", "%") for pattern in patterns)
        return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)

    def table_matches(self, coordinate: Any, datasource: str = "") -> bool:
        grant = self.datasource_grant(datasource)
        if isinstance(grant, Mapping) and grant_uses_tree_scope(grant, self._field_order):
            return datasource_scope_matches(
                grant,
                coordinate=_coordinate_mapping(coordinate, self._field_order),
                target_field="table",
                field_order=self._field_order,
            )

        return all(
            (
                self.scope_matches("catalogs", [_coordinate_value(coordinate, "catalog")], datasource),
                self.scope_matches("databases", [_coordinate_value(coordinate, "database")], datasource),
                self.scope_matches("schemas", _schema_scope_candidates(coordinate), datasource),
                self.scope_matches("tables", _table_scope_candidates(coordinate), datasource),
            )
        )

    def listing_table_matches(self, coordinate: Any, datasource: str = "") -> bool:
        if self.table_matches(coordinate, datasource):
            return True

        grant = self.datasource_grant(datasource)
        if not isinstance(grant, Mapping) or not _is_allow_grant(grant):
            return False
        table_patterns = _scope_patterns(grant, "tables")
        table = _coordinate_value(coordinate, "table")
        if not table_patterns or not table:
            return False

        for raw_pattern in table_patterns:
            pattern = _parse_scope_pattern(raw_pattern, self._field_order)
            if pattern is None or not _pattern_matches(pattern.get("table", ""), table):
                continue
            if any(
                pattern_value and coordinate_value and not _pattern_matches(pattern_value, coordinate_value)
                for pattern_value, coordinate_value in (
                    (pattern.get("catalog", ""), _coordinate_value(coordinate, "catalog")),
                    (pattern.get("database", ""), _coordinate_value(coordinate, "database")),
                    (pattern.get("schema", ""), _coordinate_value(coordinate, "schema")),
                )
            ):
                continue

            effective = {
                field: _coordinate_value(coordinate, field) or pattern.get(field, "")
                for field in ("catalog", "database", "schema", "table")
            }
            if self.table_matches(effective, datasource):
                return True
        return False

    def uses_tree_scope(self, datasource: str = "") -> bool:
        grant = self.datasource_grant(datasource)
        return isinstance(grant, Mapping) and _is_allow_grant(grant) and grant_uses_tree_scope(grant, self._field_order)

    def namespace_matches(self, coordinate: Any, namespace_field: str, datasource: str = "") -> bool:
        if not self.uses_tree_scope(datasource) or namespace_field not in self._field_order:
            return False
        grant = self.datasource_grant(datasource)
        return datasource_scope_matches(
            grant,
            coordinate=_coordinate_mapping(coordinate, self._field_order),
            target_field=namespace_field,
            field_order=self._field_order,
        )

    def datasource_grant(self, datasource: str = "") -> Any:
        grants = self._principal.get("datasource_grants")
        if not isinstance(grants, Mapping):
            return None
        datasource_key = str(datasource or self._principal.get("datasource") or self._default_datasource or "")
        return grants.get(datasource_key, grants.get("*", False))


def _scope_patterns(grant: Mapping[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    return [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]


def _schema_scope_candidates(coordinate: Any) -> list[str]:
    catalog = _coordinate_value(coordinate, "catalog")
    database = _coordinate_value(coordinate, "database")
    schema = _coordinate_value(coordinate, "schema")
    candidates = [schema] if schema else []
    if database and schema:
        candidates.append(f"{database}.{schema}")
    if catalog and schema:
        candidates.append(f"{catalog}.{schema}")
    if catalog and database and schema:
        candidates.append(f"{catalog}.{database}.{schema}")
    return candidates


def _table_scope_candidates(coordinate: Any) -> list[str]:
    catalog = _coordinate_value(coordinate, "catalog")
    database = _coordinate_value(coordinate, "database")
    schema = _coordinate_value(coordinate, "schema")
    table = _coordinate_value(coordinate, "table")
    candidates = [table] if table else []
    if schema and table:
        candidates.append(f"{schema}.{table}")
    if database and table:
        candidates.append(f"{database}.{table}")
    if database and schema and table:
        candidates.append(f"{database}.{schema}.{table}")
    if catalog and database and table:
        candidates.append(f"{catalog}.{database}.{table}")
    if catalog and database and schema and table:
        candidates.append(f"{catalog}.{database}.{schema}.{table}")
    return candidates


def _parse_scope_pattern(pattern: str, field_order: Sequence[str]) -> dict[str, str] | None:
    parts = [_normalize_identifier_part(part) for part in str(pattern).split(".") if part.strip()]
    if not parts:
        return None
    values = {field: "" for field in field_order}
    trimmed_parts = parts[-len(field_order) :]
    start_field_index = max(0, len(field_order) - len(trimmed_parts))
    for index, part in enumerate(trimmed_parts):
        values[field_order[start_field_index + index]] = part
    return values


def _coordinate_mapping(coordinate: Any, field_order: Sequence[str]) -> dict[str, str]:
    return {field: _coordinate_value(coordinate, field) for field in field_order}


def _coordinate_value(coordinate: Any, field: str) -> str:
    if isinstance(coordinate, Mapping):
        return str(coordinate.get(field, "") or "")
    return str(getattr(coordinate, field, "") or "")


def _normalize_identifier_part(value: Any) -> str:
    return str(value or "").strip().strip("`\"'[]")


def _pattern_matches(pattern: str, value: str) -> bool:
    if not pattern or pattern in ("*", "%"):
        return True
    if not value:
        return False
    return fnmatchcase(value, pattern.replace("%", "*"))


def _is_allow_grant(grant: Mapping[str, Any]) -> bool:
    return str(grant.get("effect", "allow")).strip().lower() == "allow"

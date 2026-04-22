# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Mixin interface for connectors that can serve as a cross-database migration target.

Adapters implement this Mixin to declare their dialect-specific constraints, type
hints, and optional DDL validation. The migration agent reads these through a set
of thin wrapper tools, keeping dialect knowledge out of the agent layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MigrationTargetMixin(ABC):
    """Capabilities exposed when this connector is used as a migration target.

    Only ``describe_migration_capabilities`` is mandatory. All other methods have
    sensible defaults so an adapter can declare partial support.
    """

    @abstractmethod
    def describe_migration_capabilities(self) -> Dict[str, Any]:
        """Return dialect hints and constraints for migration DDL generation.

        Recommended keys:
          * ``supported`` (bool) — whether this adapter is a usable migration target.
          * ``dialect_family`` (str) — e.g. ``"mysql-like"``, ``"postgres-like"``,
            ``"clickhouse"``, ``"trino-hive"``.
          * ``requires`` (list[str]) — clauses the DDL MUST include.
          * ``forbids`` (list[str]) — patterns the DDL MUST NOT include.
          * ``type_hints`` (dict[str, str]) — preferred type mappings (human-readable).
          * ``example_ddl`` (str) — a minimal CREATE TABLE example for the dialect.
        """

    def map_source_type(self, source_dialect: str, source_type: str) -> Optional[str]:
        """Deterministic type mapping.

        Default returns ``None`` — the LLM will decide. Adapters may override to
        enforce precision on well-known pairings (e.g. ``HUGEINT`` → ``NUMERIC(38,0)``).
        """
        return None

    def suggest_table_layout(self, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Suggest dialect-specific table layout (keys, distribution, partitioning).

        OLAP targets may return e.g.::

            {"duplicate_key": ["id"], "distributed_by": ["id"], "buckets": 10}
            {"order_by": ["id"], "engine": "MergeTree()"}
            {"partitioned_by": ["ds"]}

        Default returns an empty dict (OLTP / unspecified).
        """
        return {}

    def validate_ddl(self, ddl: str) -> List[str]:
        """Static structural check of a target-dialect CREATE TABLE DDL.

        Returns a list of error strings (empty == ok). Does not execute anything.
        """
        return []

    def dry_run_ddl(self, ddl: str, target_table: str) -> List[str]:
        """Actually CREATE the target table to a temp name and DROP it.

        Returns a list of error strings (empty == ok). This is the strongest form
        of validation. Default raises ``NotImplementedError`` — agents must catch
        and fall back to static ``validate_ddl`` only.
        """
        raise NotImplementedError("dry_run_ddl is not supported by this adapter")

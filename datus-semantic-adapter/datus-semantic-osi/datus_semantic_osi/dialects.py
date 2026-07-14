# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Resolve the sqlglot execution dialect from the Datus datasource type.

OSI expressions are authored in the active datasource's native SQL, so parsing
and re-emitting them must use that datasource's sqlglot dialect rather than a
hardcoded one.
"""

from typing import Optional

import sqlglot

# datasource type -> sqlglot dialect, only where the names differ.
_DIALECT_ALIASES = {
    "postgresql": "postgres",
    "greenplum": "postgres",
}

# Lenient fallback when the datasource is unknown or maps to no sqlglot dialect.
DEFAULT_SQLGLOT_DIALECT = "mysql"


def resolve_sqlglot_dialect(datasource: Optional[str]) -> str:
    """Return the sqlglot dialect name for a Datus datasource type."""
    name = str(datasource or "").strip().lower()
    name = _DIALECT_ALIASES.get(name, name)
    if name and name in sqlglot.Dialect.classes:
        return name
    return DEFAULT_SQLGLOT_DIALECT

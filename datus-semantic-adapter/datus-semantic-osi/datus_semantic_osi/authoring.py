# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""OSI metric authoring.

The file read/write/delete/validate machinery lives in
``datus_semantic_core.metric_author.MetricAuthor`` (shared with the osi_engine
adapter). This module specializes it for the Python OSI compiler adapter:
document validation runs the full OSI jsonschema + profile parse, and
structural failures keep raising :class:`OSIValidationError` for backward
compatibility.
"""

from __future__ import annotations

from typing import Any, Dict

# Re-exported for backward compatibility (tests / callers import these here).
from datus_semantic_core.metric_author import (  # noqa: F401
    MetricAuthor,
    _datus_hints,
    _set_datus_hints,
    json_clone,
)

from .errors import OSIValidationError
from .profile import CORE_SCHEMA_VERSION, parse_osi, validate_osi_core_schema

FORMAT = "osi"


def _osi_validate_document(doc: Dict[str, Any]) -> None:
    """Full OSI validation of a core document: jsonschema + profile parse."""
    validate_osi_core_schema(doc)
    parse_osi(doc)  # runs merge + profile parsing, surfacing structural errors


class OSIMetricAuthor(MetricAuthor):
    """MetricAuthor wired with strict OSI validation and OSI error semantics."""

    def __init__(self, semantic_models_path: str):
        super().__init__(
            semantic_models_path,
            validate_document=_osi_validate_document,
            schema_version=CORE_SCHEMA_VERSION,
            error_cls=OSIValidationError,
        )

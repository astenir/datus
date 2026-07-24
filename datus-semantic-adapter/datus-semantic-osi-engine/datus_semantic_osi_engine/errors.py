# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Mapping from the engine's structured exceptions to core error shapes.

The engine's ``QueryError`` already carries stable codes and candidates —
this module only reshapes them into ``SemanticValidationError`` (agent-facing,
retryable) or ``SemanticCoreException`` (infrastructure, not retryable).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from datus_semantic_core.exceptions import SemanticCoreException
from datus_semantic_core.models import SemanticValidationError

# Planner rejections an agent can fix by revising the query.
_RETRYABLE_QUERY_CODES = {
    "unknown_metric",
    "unknown_dimension",
    "ambiguous_dimension",
    "grain_on_non_time_dimension",
    "duplicate_output_name",
    "unknown_order_key",
    "unsupported_filter",
    "aggregate_in_where",
    "no_join_path",
    "ambiguous_join_path",
    "fan_out_risk",
    "time_range_needs_dimension",
    "empty_query",
}


class SemanticValidationException(Exception):
    """A deterministic query rejection carrying a structured payload.

    ``payload`` is a ``SemanticValidationError`` so callers revise arguments
    from stable fields instead of parsing exception text.
    """

    def __init__(self, payload: SemanticValidationError):
        self.payload = payload
        super().__init__(payload.message or "semantic validation error")


def _message_with_context(exc: Any) -> str:
    parts = [str(getattr(exc, "message", "") or exc)]
    candidates = list(getattr(exc, "candidates", ()) or ())
    if candidates:
        parts.append(f"candidates: {', '.join(candidates)}")
    hint = getattr(exc, "hint", None)
    if hint:
        parts.append(str(hint))
    return " | ".join(parts)


def validation_error_from_query_error(
    exc: Any,
    *,
    requested_metrics: Optional[List[str]] = None,
    requested_dimensions: Optional[List[str]] = None,
) -> SemanticValidationError:
    """Reshape an engine ``QueryError`` into a ``SemanticValidationError``.

    The engine's ``candidates`` become a concrete ``suggested_retry`` only
    when the fix is unambiguous (exactly one candidate); otherwise they stay
    in the message for the agent to choose from.
    """
    code = str(getattr(exc, "code", "") or "validation_error")
    candidates = list(getattr(exc, "candidates", ()) or ())

    suggested_retry: Optional[Dict[str, Any]] = None
    if len(candidates) == 1:
        if code == "unknown_metric":
            suggested_retry = {"metrics": candidates}
        elif code in {"unknown_dimension", "ambiguous_dimension"}:
            suggested_retry = {
                "metrics": list(requested_metrics or []),
                "dimensions": candidates,
            }

    unsupported_dimensions: List[str] = []
    if code in {"unknown_dimension", "ambiguous_dimension"}:
        # The offending name is whichever requested dimension is not itself
        # a valid candidate; with no request context this stays empty.
        unsupported_dimensions = [
            d for d in (requested_dimensions or []) if d not in candidates
        ]

    return SemanticValidationError(
        code=code,
        metrics=list(getattr(exc, "metrics", ()) or ()) or list(requested_metrics or []),
        unsupported_dimensions=unsupported_dimensions,
        suggested_retry=suggested_retry,
        message=_message_with_context(exc),
    )


def raise_mapped(exc: Any, binding: Any, **request_context: Any) -> None:
    """Re-raise an engine exception in the adapter's vocabulary.

    Retryable planner rejections become ``SemanticValidationException``;
    model/execution/config failures become ``SemanticCoreException``.
    """
    if isinstance(exc, binding.QueryError) and exc.code in _RETRYABLE_QUERY_CODES:
        raise SemanticValidationException(
            validation_error_from_query_error(exc, **request_context)
        ) from exc
    if isinstance(exc, binding.OsiError):
        raise SemanticCoreException(
            f"osi-engine {type(exc).__name__} [{exc.code}]: {_message_with_context(exc)}"
        ) from exc
    raise exc

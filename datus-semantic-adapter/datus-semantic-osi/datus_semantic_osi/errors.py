# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus OSI errors.

Errors raised during OSI -> IR compilation are *business-semantic*: they tell a
metric author what business input is missing (numerator, window, time dimension,
fixed row scope), never a backend syntax detail like ``type_params.measures``.
"""

from __future__ import annotations

from typing import Optional


class OSIError(Exception):
    """Base class for all Datus OSI errors."""


class OSIValidationError(OSIError):
    """A metric/dataset cannot be safely compiled; the message is business-facing.

    Attributes:
        metric: The metric name the error relates to, if any.
        hint: A concrete remediation, phrased as business semantics to declare.
    """

    def __init__(
        self, message: str, *, metric: Optional[str] = None, hint: Optional[str] = None
    ):
        self.metric = metric
        self.hint = hint
        parts = []
        if metric:
            parts.append(f"Metric `{metric}`:")
        parts.append(message)
        if hint:
            parts.append(hint)
        super().__init__(" ".join(parts))


class OSICompileError(OSIError):
    """An internal compilation failure not attributable to author input."""


class SemanticValidationException(OSIError):
    """A deterministic query validation rejection carrying a structured payload.

    Raised by ``query_metrics`` when the backend rejects a query for validation
    reasons (e.g. a metric that must be grouped by metric_time). The ``payload``
    is a ``datus_semantic_core.models.SemanticValidationError`` so callers can
    revise arguments from stable fields instead of parsing exception text.
    """

    def __init__(self, payload):
        self.payload = payload
        super().__init__(getattr(payload, "message", "") or "semantic validation error")

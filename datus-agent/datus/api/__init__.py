# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Datus Agent FastAPI service package.
"""

from typing import Any

from .legacy_models import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    RunWorkflowRequest,
    RunWorkflowResponse,
    TokenResponse,
)


def __getattr__(name: str) -> Any:
    if name in {"create_app", "service"}:
        from .service import create_app, service

        return {"create_app": create_app, "service": service}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "create_app",
    "service",
    "RunWorkflowRequest",
    "RunWorkflowResponse",
    "HealthResponse",
    "TokenResponse",
    "FeedbackRequest",
    "FeedbackResponse",
]

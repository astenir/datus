# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from pydantic import BaseModel, ConfigDict, Field


class ConnectionConfig(BaseModel):
    """Base connection configuration for all database connectors."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(
        default=30, description="Connection timeout in seconds"
    )

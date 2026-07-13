# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Base configuration for semantic adapters."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SemanticAdapterConfig(BaseModel):
    """Base configuration for semantic adapters."""

    model_config = ConfigDict(extra="allow")

    datasource: Optional[str] = Field(default=None, description="Datus datasource for configuration")
    timeout_seconds: int = Field(default=30, description="Operation timeout in seconds")
    api_base_url: Optional[str] = Field(default=None, description="API base URL")
    auth_token: Optional[str] = Field(default=None, description="Auth token (JWT, API key, service token)")
    username: Optional[str] = Field(default=None, description="Username for basic auth or token exchange")
    password: Optional[str] = Field(
        default=None,
        description="Password for basic auth or token exchange",
        json_schema_extra={"input_type": "password"},
    )

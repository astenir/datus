# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrinoConfig(BaseModel):
    """Trino-specific configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(default="127.0.0.1", description="Trino server host")
    port: int = Field(default=8080, description="Trino server port")
    username: str = Field(..., description="Trino username")
    password: str = Field(default="", description="Trino password", json_schema_extra={"input_type": "password"})
    catalog: str = Field(default="hive", description="Default catalog name")
    schema_name: str = Field(default="default", description="Default schema name")
    http_scheme: Literal["http", "https"] = Field(default="http", description="HTTP scheme (http or https)")
    verify: bool = Field(default=True, description="Verify SSL certificates")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

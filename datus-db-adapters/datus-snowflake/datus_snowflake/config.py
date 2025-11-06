# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SnowflakeConfig(BaseModel):
    """Snowflake-specific configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    account: str = Field(..., description="Snowflake account identifier")
    username: str = Field(..., description="Snowflake username")
    password: str = Field(..., description="Snowflake password")
    warehouse: str = Field(..., description="Snowflake warehouse name")
    database: Optional[str] = Field(default=None, description="Default database name")
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Default schema name")
    role: Optional[str] = Field(default=None, description="Snowflake role to use")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

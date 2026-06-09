# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import re
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


def _base_username(username: str) -> str:
    return re.split(r"[@#]", username, maxsplit=1)[0]


class OceanBaseOracleConfig(BaseModel):
    """OceanBase Oracle mode configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(default="127.0.0.1", description="OceanBase server host")
    port: int = Field(default=2883, description="OceanBase server port")
    username: str = Field(..., description="Username in format user@tenant#cluster")
    password: str = Field(
        default="",
        description="Password",
        json_schema_extra={"input_type": "password"},
    )
    database: Optional[str] = Field(default=None, description="OceanBase tenant name")
    schema_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("schema_name", "schema"),
        description="Default Oracle schema name (user/owner)",
    )
    jar_path: str = Field(..., description="Path to oceanbase-client JDBC jar file")
    driver_class: str = Field(
        default="com.oceanbase.jdbc.Driver",
        description="JDBC driver class name",
    )
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @model_validator(mode="before")
    @classmethod
    def prefer_explicit_names(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "schema_name" in normalized and "schema" in normalized:
            normalized.pop("schema")
        return normalized

    @model_validator(mode="after")
    def normalize_names(self):
        if self.schema_name:
            self.schema_name = self.schema_name.upper()
        else:
            self.schema_name = _base_username(self.username).upper()
        return self

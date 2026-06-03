# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class OracleConfig(BaseModel):
    """Oracle-specific configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(default="127.0.0.1", description="Oracle server host")
    port: int = Field(default=1521, description="Oracle listener port")
    username: str = Field(..., description="Oracle username")
    password: str = Field(
        default="",
        description="Oracle password",
        json_schema_extra={"input_type": "password"},
    )
    service_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("service_name", "database"),
        description="Oracle service name",
    )
    sid: Optional[str] = Field(default=None, description="Oracle SID; mutually exclusive with service_name")
    schema_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("schema_name", "schema"),
        description="Default Oracle schema/owner",
    )
    thick_mode: bool = Field(default=False, description="Use python-oracledb thick mode")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @model_validator(mode="before")
    @classmethod
    def prefer_explicit_names(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "service_name" in normalized and "database" in normalized:
            normalized.pop("database")
        if "schema_name" in normalized and "schema" in normalized:
            normalized.pop("schema")
        return normalized

    @model_validator(mode="after")
    def normalize_oracle_names(self):
        if self.service_name and self.sid:
            raise ValueError("service_name/database and sid are mutually exclusive")
        if not self.service_name and not self.sid:
            self.service_name = "FREEPDB1"
        if not self.schema_name:
            self.schema_name = self.username.upper()
        else:
            self.schema_name = self.schema_name.upper()
        return self

    @property
    def database(self) -> str:
        return self.service_name or self.sid or ""

# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SnowflakeConfig(BaseModel):
    """Snowflake-specific configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, coerce_numbers_to_str=True)

    account: str = Field(..., description="Snowflake account identifier")
    username: str = Field(..., description="Snowflake username")
    password: Optional[str] = Field(
        default=None,
        description="Snowflake password (omit when using key pair authentication)",
        json_schema_extra={"input_type": "password"},
    )
    private_key_file: Optional[str] = Field(
        default=None,
        description="Path to PEM-encoded RSA private key for key pair authentication (SNOWFLAKE_JWT)",
    )
    private_key_file_pwd: Optional[str] = Field(
        default=None,
        description="Passphrase for the encrypted private key file (omit for unencrypted keys)",
        json_schema_extra={"input_type": "password"},
    )
    warehouse: str = Field(..., description="Snowflake warehouse name")
    database: Optional[str] = Field(default=None, description="Default database name")
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Default schema name")
    role: Optional[str] = Field(default=None, description="Snowflake role to use")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @model_validator(mode="after")
    def _require_exactly_one_credential(self) -> "SnowflakeConfig":
        has_password = bool(self.password)
        has_key = bool(self.private_key_file)
        if has_password == has_key:
            raise ValueError(
                "SnowflakeConfig requires exactly one of `password` or `private_key_file` "
                "(use key pair authentication for MFA-enforced accounts)"
            )
        return self

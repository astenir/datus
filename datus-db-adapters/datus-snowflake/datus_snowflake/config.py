# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class SnowflakeConfig(BaseModel):
    """Snowflake-specific configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, coerce_numbers_to_str=True)

    account: str = Field(..., description="Snowflake account identifier")
    username: str = Field(..., description="Snowflake username")
    password: Optional[SecretStr] = Field(
        default=None,
        description="Snowflake password (omit when using key pair authentication)",
        json_schema_extra={"input_type": "password"},
    )
    private_key_file: Optional[str] = Field(
        default=None,
        description="Path to PEM-encoded RSA private key for key pair authentication (SNOWFLAKE_JWT)",
    )
    private_key: Optional[SecretStr] = Field(
        default=None,
        description=(
            "PEM-encoded RSA private key for key pair authentication (SNOWFLAKE_JWT); "
            "takes precedence over private_key_file and password"
        ),
        json_schema_extra={"input_type": "password"},
    )
    private_key_file_pwd: Optional[SecretStr] = Field(
        default=None,
        description="Passphrase for the encrypted private key file (omit for unencrypted keys)",
        json_schema_extra={"input_type": "password"},
    )
    warehouse: str = Field(..., description="Snowflake warehouse name")
    database: Optional[str] = Field(default=None, description="Default database name")
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Default schema name")
    role: Optional[str] = Field(default=None, description="Snowflake role to use")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @staticmethod
    def _has_secret(value: Optional[SecretStr]) -> bool:
        return value is not None and bool(value.get_secret_value())

    @model_validator(mode="after")
    def _require_supported_credential(self) -> "SnowflakeConfig":
        has_private_key = self._has_secret(self.private_key)
        if has_private_key:
            return self

        has_password = self._has_secret(self.password)
        has_key = bool(self.private_key_file)
        if has_password == has_key:
            raise ValueError(
                "SnowflakeConfig requires `private_key`, or exactly one of `password` "
                "or `private_key_file` (private_key takes precedence when provided)"
            )
        return self

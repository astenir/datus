# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import re
from typing import Dict, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


def _base_username(username: str) -> str:
    return re.split(r"[@#]", username, maxsplit=1)[0]


class OceanBaseOracleConfig(BaseModel):
    """OceanBase Oracle mode configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(default="127.0.0.1", description="OceanBase server host")
    port: int = Field(default=2883, ge=1, le=65535, description="OceanBase server port (2883 for ODP, 2881 for direct)")
    username: str = Field(..., description="Username in format user@tenant#cluster (ODP) or user@tenant (direct)")
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
    connection_mode: Literal["odp", "direct"] = Field(
        default="odp",
        description="Connection mode: 'odp' via OceanBase Database Proxy (port 2883), 'direct' to OBServer (port 2881)",
    )
    use_ssl: bool = Field(default=False, description="Enable SSL for JDBC connection")
    connect_timeout_seconds: int = Field(default=30, gt=0, description="JDBC connection timeout in seconds")
    query_timeout_seconds: int = Field(
        default=30, gt=0, description="Query timeout in seconds (set via ob_query_timeout)"
    )
    timeout_seconds: int = Field(default=30, description="General timeout in seconds (kept for backward compatibility)")
    pool_maxconnections: int = Field(default=10, ge=1, description="Maximum number of connections in the pool")
    pool_mincached: int = Field(default=2, ge=0, description="Minimum number of idle connections kept in the pool")
    pool_maxcached: int = Field(default=5, ge=0, description="Maximum number of idle connections kept in the pool")
    pool_blocking: bool = Field(default=True, description="Block when pool is exhausted instead of raising error")
    pool_ping_timeout_seconds: int = Field(
        default=5,
        gt=0,
        description="JDBC connection validation timeout in seconds when borrowing from the pool",
    )
    extra_jdbc_params: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional JDBC URL parameters, e.g. {'useUnicode': 'true', 'characterEncoding': 'utf-8'}",
    )

    @model_validator(mode="before")
    @classmethod
    def prefer_explicit_names(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "schema_name" in normalized and "schema" in normalized:
            normalized.pop("schema")
        return normalized

    @model_validator(mode="before")
    @classmethod
    def set_default_port_for_mode(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if normalized.get("connection_mode") == "direct" and "port" not in normalized:
            normalized["port"] = 2881
        return normalized

    @model_validator(mode="after")
    def normalize_names(self):
        if self.schema_name:
            self.schema_name = self.schema_name.upper()
        else:
            self.schema_name = _base_username(self.username).upper()
        return self

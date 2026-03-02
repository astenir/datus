# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field


def _extract_prefixed_config(carrier_map: Mapping[str, Any], prefix: str) -> Dict[str, Any]:
    """Extract Hive configuration from a prefixed carrier map."""
    hive_config: Dict[str, Any] = {}
    prefix_len = len(prefix)

    for key, value in carrier_map.items():
        if key.startswith(prefix):
            kyuubi_key = key[prefix_len:]
            hive_config[kyuubi_key] = value

    configuration_params: Dict[str, Any] = {}
    base_params: Dict[str, Any] = {}

    for key, value in hive_config.items():
        if key.startswith("configuration."):
            config_key = key[14:]
            configuration_params[config_key] = value
        else:
            if key == "port" and isinstance(value, str) and value.isdigit():
                base_params[key] = int(value)
            else:
                base_params[key] = value

    result = base_params.copy()
    result["configuration"] = configuration_params
    return result


class HiveConfig(BaseModel):
    """Hive-specific configuration."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(default="127.0.0.1", description="Hive server host")
    port: int = Field(default=10000, description="Hive server port")
    database: Optional[str] = Field(default=None, description="Default database name")
    username: str = Field(..., description="Hive username")
    password: str = Field(default="", description="Hive password", json_schema_extra={"input_type": "password"})
    auth: Optional[str] = Field(default=None, description="Authentication mechanism (NONE, LDAP, CUSTOM, KERBEROS)")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Hive session configuration")
    timeout_seconds: int = Field(default=30, description="Connection timeout in seconds")

    @classmethod
    def from_config_map(cls, config_map: Mapping[str, Any], prefix: str) -> "HiveConfig":
        """Build HiveConfig from a prefixed carrier map."""
        extracted = _extract_prefixed_config(config_map, prefix)
        return cls(**extracted)

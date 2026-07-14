from typing import Dict, Optional

from datus_semantic_core import SemanticAdapterConfig
from pydantic import Field


class MetricFlowConfig(SemanticAdapterConfig):
    """Configuration for MetricFlow adapter."""

    service_type: str = Field(default="metricflow", description="Service type")
    config_path: Optional[str] = Field(None, description="Path to MetricFlow configuration file")
    timeout: int = Field(default=300, description="Query timeout in seconds")
    db_config: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Database config dict (type, host, port, username, password, "
            "private_key_file, database, schema, uri, etc.)"
        ),
    )
    agent_home: Optional[str] = Field(None, description="Datus agent home path, for resolving model_path")
    semantic_models_path: Optional[str] = Field(
        None, description="Path to semantic model YAML directory. Overrides default {agent_home}/semantic_models/{datasource}."
    )

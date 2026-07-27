"""Downstream project-overlay coverage for external datasource files."""

from unittest.mock import patch

from datus.configuration.agent_config_loader import _apply_project_override
from datus.configuration.project_config import ProjectOverride


def test_default_datasource_can_target_datasources_file_entry(tmp_path):
    datasources_file = tmp_path / "datasources.yml"
    datasources_file.write_text(
        """
datasources:
  external_pg:
    type: postgresql
    host: pg-host
    database: warehouse
""",
        encoding="utf-8",
    )
    agent_raw = {
        "target": "openai",
        "models": {"openai": {"type": "openai"}},
        "services": {
            "datasources": {
                "db1": {"type": "sqlite"},
                "db2": {"type": "duckdb"},
            },
            "datasources_file": str(datasources_file),
        },
    }
    with patch(
        "datus.configuration.agent_config_loader.load_project_override",
        return_value=ProjectOverride(default_datasource="external_pg"),
    ):
        _apply_project_override(agent_raw)

    assert agent_raw["services"]["datasources"]["external_pg"]["default"] is True
    assert agent_raw["services"]["datasources"]["db1"]["default"] is False
    assert agent_raw["services"]["datasources_file"] == ""

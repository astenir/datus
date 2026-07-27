"""Tests for enterprise datasource status extensions."""

from datus.api.models.database_models import ListDatabasesInput
from datus_enterprise.services.database_service import EnterpriseDatasourceService


def test_status_is_unknown_before_first_connection(real_agent_config):
    """Status lookup does not open datasource connections."""
    svc = EnterpriseDatasourceService(agent_config=real_agent_config)

    statuses = svc.datasource_statuses(["california_schools"])

    assert statuses[0].datasource_id == "california_schools"
    assert statuses[0].status == "unknown"
    assert statuses[0].cached is False
    assert svc.current_db_connector is None


def test_status_updates_after_catalog_load(real_agent_config):
    """Successful catalog loading records a cached connected status."""
    svc = EnterpriseDatasourceService(agent_config=real_agent_config)

    result = svc.list_databases(ListDatabasesInput())
    statuses = svc.datasource_statuses(["california_schools"])

    assert result.success is True
    assert statuses[0].status == "connected"
    assert statuses[0].cached is True
    assert statuses[0].latency_ms is not None

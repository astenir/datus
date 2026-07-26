"""Downstream tests for datasource service extensions."""

from datus.api.models.database_models import ListDatabasesInput
from datus.api.services.database_service import DatasourceService
from datus.configuration.agent_config import DbConfig
from datus.tools.db_tools.db_manager import DBManager
from datus_enterprise.services.database_service import EnterpriseDatasourceService
from tests.unit_tests.api.services.test_database_service import (
    _FakeServerConnector,
)
from tests.unit_tests.api.services.test_database_service import (
    _no_schema_dialect as _no_schema_dialect,
)


class _FakeViewConnector(_FakeServerConnector):
    """No-schema connector with queryable views for catalog listing."""

    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        return ["v_orders", "v_customers"]

    def get_materialized_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        return ["mv_rollup"]


class TestDatasourceServiceInit:
    def test_init_reuses_request_scoped_db_manager(self, real_agent_config):
        """Request-scoped services may share the connector cache without shared selection state."""
        db_manager = DBManager(real_agent_config.datasource_configs)

        svc = DatasourceService(agent_config=real_agent_config, db_manager=db_manager)

        assert svc.db_manager is db_manager


class TestGetConnectionInfoScoping:
    def test_catalog_listing_includes_views_for_grant_picker(self, real_agent_config, _no_schema_dialect):
        """Catalog entries include views so datasource-grant pickers can authorize them."""
        svc = EnterpriseDatasourceService(agent_config=real_agent_config)
        connector = _FakeViewConnector(database_name="benchmark")

        infos = svc._get_connection_info(connector, "benchmark", ListDatabasesInput())

        assert infos[0].tables == ["mv_rollup", "t1", "t2", "v_customers", "v_orders"]
        assert infos[0].tables_count == 5

    def test_explicit_enumerate_databases_lists_server_databases(self, real_agent_config, _no_schema_dialect):
        """A server datasource may opt into instance-wide catalog listing."""
        real_agent_config.services.datasources["warehouse"] = DbConfig(
            type="starrocks",
            database="benchmark",
            enumerate_databases=True,
        )
        svc = EnterpriseDatasourceService(agent_config=real_agent_config)
        connector = _FakeServerConnector(database_name="benchmark")

        infos = svc._get_connection_info(connector, "warehouse", ListDatabasesInput())

        assert connector.get_databases_calls == 1
        assert [i.name for i in infos] == ["benchmark", "ga4", "olist", "fund_poc"]

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

    def test_default_db_manager_shares_process_wide_instance(self, real_agent_config):
        """Without an explicit db_manager, the service resolves the process-wide
        shared instance (db_manager_instance), so schema/table browsing reuses
        the same warm connectors as the AI query path for public datasources."""
        from datus.tools.db_tools.db_manager import db_manager_instance

        svc1 = DatasourceService(agent_config=real_agent_config)
        svc2 = DatasourceService(agent_config=real_agent_config)

        assert svc1.db_manager is svc2.db_manager
        assert svc1.db_manager is db_manager_instance(real_agent_config.datasource_configs)


class TestMetadataListingCache:
    def test_catalog_listing_reuses_cached_metadata_within_ttl(self, real_agent_config, _no_schema_dialect):
        """Repeated catalog expands within the TTL reuse the cached listing
        instead of re-querying the connector for every request."""
        svc = DatasourceService(agent_config=real_agent_config)
        connector = _FakeServerConnector(database_name="")

        svc._get_connection_info(connector, "ds", ListDatabasesInput())
        assert connector.get_databases_calls == 1
        svc._get_connection_info(connector, "ds", ListDatabasesInput())
        assert connector.get_databases_calls == 1

    def test_catalog_listing_cache_expires_after_ttl(self, real_agent_config, _no_schema_dialect):
        """Once the TTL elapses the connector is queried again."""
        svc = DatasourceService(agent_config=real_agent_config)
        svc._METADATA_CACHE_TTL = -1.0
        connector = _FakeServerConnector(database_name="")

        svc._get_connection_info(connector, "ds", ListDatabasesInput())
        svc._get_connection_info(connector, "ds", ListDatabasesInput())
        assert connector.get_databases_calls == 2

    def test_table_listing_cached_per_schema(self, real_agent_config, _no_schema_dialect):
        """Table lists are cached per (datasource, database, schema) so different
        databases keep distinct entries while repeats hit the cache."""
        svc = DatasourceService(agent_config=real_agent_config)
        connector = _FakeServerConnector(database_name="")

        first = svc._get_connection_info(connector, "ds", ListDatabasesInput())
        second = svc._get_connection_info(connector, "ds", ListDatabasesInput())

        assert [i.name for i in first] == [i.name for i in second]
        assert first[0].tables == second[0].tables


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

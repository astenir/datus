"""
Test cases for DBFuncTool compressor model_name initialization and execute_ddl.
"""

from typing import Any
from unittest.mock import Mock, patch

from datus.tools.func_tool.database import DBFuncTool
from datus.tools.sql_policy import EnforcementResult, SqlPolicyConfig


class DenySqlPolicyEnforcer:
    def __init__(self, config: SqlPolicyConfig) -> None:
        self.config = config

    def enforce_read(
        self, sql: str, *, datasource: str, dialect: str, principal: dict[str, Any] | None
    ) -> EnforcementResult:
        return EnforcementResult(allowed=False, reason="transfer source denied")


class TestDBFuncToolExecuteDDLDownstream:
    """Tests for DBFuncTool.execute_ddl method."""

    def _make_tool(self, connector):
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            return DBFuncTool(connector)

    def test_execute_ddl_rejects_ctas_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "sqlite"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_ddl("CREATE TABLE archived_orders AS SELECT * FROM orders")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_create_table_as_table_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_ddl("CREATE TABLE archived_orders AS TABLE orders")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_create_table_as_table_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl("CREATE TABLE archived_orders AS TABLE orders")
        assert result.success == 0
        assert "outside scoped context" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_create_table_as_table_only_source_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl("CREATE TABLE archived_orders AS TABLE ONLY orders")
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        assert "ONLY" not in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_parenthesized_table_expression_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archive"])
        result = tool.execute_ddl("CREATE TABLE archive AS (TABLE orders)")
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_quoted_create_table_as_table_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl('CREATE TABLE "archived_orders" AS TABLE "orders"')
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_attach_partition_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl("ALTER TABLE archived_orders ATTACH PARTITION orders FOR VALUES IN (1)")
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_quoted_attach_partition_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl('ALTER TABLE "archived_orders" ATTACH PARTITION "orders" FOR VALUES IN (1)')
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_ddl.assert_not_called()

    def test_execute_ddl_rejects_exchange_partition_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "mysql"
        mock_connector.schema_name = "public"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_ddl.return_value = Mock(success=True)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archived_orders"])
        result = tool.execute_ddl("ALTER TABLE archived_orders EXCHANGE PARTITION p1 WITH TABLE orders")
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_ddl.assert_not_called()


class TestDBFuncToolExecuteWriteDownstream:
    """Tests for DBFuncTool.execute_write method."""

    def _make_tool(self, connector=None):
        if connector is None:
            connector = Mock()
            connector.dialect = "sqlite"
            connector.get_databases.return_value = []
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            return DBFuncTool(connector)

    def test_execute_write_rejects_insert_select_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "sqlite"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_insert.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("INSERT INTO archive SELECT * FROM orders")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_insert.assert_not_called()

    def test_execute_write_rejects_update_subquery_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "sqlite"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_update.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("UPDATE archive SET total = (SELECT COUNT(*) FROM orders)")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_update.assert_not_called()

    def test_execute_write_rejects_update_from_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_update.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("UPDATE archive SET total = orders.total FROM orders WHERE archive.id = orders.id")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_update.assert_not_called()

    def test_execute_write_rejects_delete_using_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_delete.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("DELETE FROM archive USING orders WHERE archive.id = orders.id")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_delete.assert_not_called()

    def test_execute_write_rejects_delete_table_expression_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_delete.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("DELETE FROM archive WHERE id IN (TABLE orders)")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_delete.assert_not_called()

    def test_execute_write_rejects_insert_table_expression_denied_by_sql_policy(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.get_databases.return_value = []
        mock_connector.execute_insert.return_value = Mock(success=True, row_count=1)
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, agent_config=agent_config)
        result = tool.execute_write("INSERT INTO archive TABLE orders")
        assert result.success == 0
        assert "transfer source denied" in result.error
        mock_connector.execute_insert.assert_not_called()

    def test_execute_write_rejects_delete_table_expression_outside_scoped_context(self):
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.schema_name = "public"
        mock_connector.execute_delete.return_value = Mock(success=True, row_count=1)
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.archive"])
        result = tool.execute_write("DELETE FROM archive WHERE id IN (TABLE orders)")
        assert result.success == 0
        assert "outside scoped context" in result.error
        assert "orders" in result.error
        mock_connector.execute_delete.assert_not_called()


class TestGetConnectorRoutingDownstream:
    """Tests for _get_connector routing in single vs multi connector mode.

    Verifies that single-connector mode ignores the database parameter
    (always returning the primary connector), while multi-connector mode
    correctly routes to different connectors by logical name.
    """

    def _make_single_mode_tool(self, connector):
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            return DBFuncTool(connector)

    def test_read_query_scoped_context_uses_requested_datasource_connector(self):
        """Scope validation must use the routed datasource, not the primary connector defaults."""
        from datus.tools.db_tools.db_manager import DBManager

        primary_connector = Mock()
        primary_connector.dialect = "sqlite"
        primary_connector.database_name = "allowed_db"
        primary_connector.get_databases.return_value = []
        secondary_connector = Mock()
        secondary_connector.dialect = "sqlite"
        secondary_connector.database_name = "forbidden_db"
        secondary_connector.get_databases.return_value = []
        secondary_connector.execute_query.return_value = Mock(success=True, sql_return=[{"id": 1}])
        mock_db_manager = Mock(spec=DBManager)
        mock_db_manager.get_conn.side_effect = lambda datasource, database="": (
            secondary_connector if datasource == "other" else primary_connector
        )
        mock_db_manager.first_conn.return_value = primary_connector
        mock_config = Mock()
        mock_config.active_model.return_value.model = "gpt-5.4"
        mock_config.current_datasource = "default"
        mock_config.current_db_configs.return_value = {"default": Mock(), "other": Mock()}
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(
                mock_db_manager,
                agent_config=mock_config,
                default_datasource="default",
                scoped_tables=["allowed_db.orders"],
            )
        result = tool.read_query("SELECT * FROM orders", datasource="other")
        assert result.success == 0
        assert "outside scoped context" in result.error
        secondary_connector.execute_query.assert_not_called()

    def test_read_query_rejects_unqualified_table_when_scoped_schema_cannot_be_resolved(self):
        """Schema-qualified scopes must fail closed when the query/connector cannot prove the schema."""
        mock_connector = Mock()
        mock_connector.dialect = "postgresql"
        mock_connector.database_name = ""
        mock_connector.schema_name = ""
        mock_connector.get_databases.return_value = []
        mock_connector.execute_query.return_value = Mock(success=True, sql_return=[{"id": 1}])
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(mock_connector, scoped_tables=["public.orders"])
        result = tool.read_query("SELECT * FROM orders")
        assert result.success == 0
        assert "outside scoped context" in result.error
        mock_connector.execute_query.assert_not_called()

    def test_execute_write_scoped_context_uses_requested_datasource_connector(self):
        """Write scope validation must use the routed datasource before executing."""
        from datus.tools.db_tools.db_manager import DBManager

        primary_connector = Mock()
        primary_connector.dialect = "sqlite"
        primary_connector.database_name = "allowed_db"
        primary_connector.get_databases.return_value = []
        secondary_connector = Mock()
        secondary_connector.dialect = "sqlite"
        secondary_connector.database_name = "forbidden_db"
        secondary_connector.get_databases.return_value = []
        secondary_connector.execute_update.return_value = Mock(success=True, row_count=1)
        mock_db_manager = Mock(spec=DBManager)
        mock_db_manager.get_conn.side_effect = lambda datasource, database="": (
            secondary_connector if datasource == "other" else primary_connector
        )
        mock_db_manager.first_conn.return_value = primary_connector
        mock_config = Mock()
        mock_config.active_model.return_value.model = "gpt-5.4"
        mock_config.current_datasource = "default"
        mock_config.current_db_configs.return_value = {"default": Mock(), "other": Mock()}
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(
                mock_db_manager,
                agent_config=mock_config,
                default_datasource="default",
                scoped_tables=["allowed_db.orders"],
            )
        result = tool.execute_write("UPDATE orders SET status = 'closed'", datasource="other")
        assert result.success == 0
        assert "outside scoped context" in result.error
        secondary_connector.execute_update.assert_not_called()

    def test_execute_ddl_scoped_context_uses_requested_datasource_connector(self):
        """DDL scope validation must use the routed datasource before executing."""
        from datus.tools.db_tools.db_manager import DBManager

        primary_connector = Mock()
        primary_connector.dialect = "sqlite"
        primary_connector.database_name = "allowed_db"
        primary_connector.get_databases.return_value = []
        secondary_connector = Mock()
        secondary_connector.dialect = "sqlite"
        secondary_connector.database_name = "forbidden_db"
        secondary_connector.get_databases.return_value = []
        secondary_connector.execute_ddl.return_value = Mock(success=True)
        mock_db_manager = Mock(spec=DBManager)
        mock_db_manager.get_conn.side_effect = lambda datasource, database="": (
            secondary_connector if datasource == "other" else primary_connector
        )
        mock_db_manager.first_conn.return_value = primary_connector
        mock_config = Mock()
        mock_config.active_model.return_value.model = "gpt-5.4"
        mock_config.current_datasource = "default"
        mock_config.current_db_configs.return_value = {"default": Mock(), "other": Mock()}
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(
                mock_db_manager,
                agent_config=mock_config,
                default_datasource="default",
                scoped_tables=["allowed_db.orders"],
            )
        result = tool.execute_ddl("DROP TABLE orders", datasource="other")
        assert result.success == 0
        assert "outside scoped context" in result.error
        secondary_connector.execute_ddl.assert_not_called()

    def test_get_table_ddl_scoped_context_uses_requested_datasource_connector(self):
        """DDL metadata scope validation must use the requested datasource defaults."""
        from datus.tools.db_tools.db_manager import DBManager

        primary_connector = Mock()
        primary_connector.dialect = "sqlite"
        primary_connector.database_name = "allowed_db"
        primary_connector.get_databases.return_value = []
        secondary_connector = Mock()
        secondary_connector.dialect = "sqlite"
        secondary_connector.database_name = "forbidden_db"
        secondary_connector.get_databases.return_value = []
        secondary_connector.get_tables_with_ddl.return_value = [
            {"database_name": "forbidden_db", "table_name": "orders", "definition": "CREATE TABLE orders (id INTEGER)"}
        ]
        mock_db_manager = Mock(spec=DBManager)
        mock_db_manager.get_conn.side_effect = lambda datasource, database="": (
            secondary_connector if datasource == "other" else primary_connector
        )
        mock_db_manager.first_conn.return_value = primary_connector
        mock_config = Mock()
        mock_config.active_model.return_value.model = "gpt-5.4"
        mock_config.current_datasource = "default"
        mock_config.current_db_configs.return_value = {"default": Mock(), "other": Mock()}
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(
                mock_db_manager,
                agent_config=mock_config,
                default_datasource="default",
                scoped_tables=["allowed_db.orders"],
            )
        result = tool.get_table_ddl("orders", datasource="other")
        assert result.success == 0
        assert "outside the scoped context" in result.error
        secondary_connector.get_tables_with_ddl.assert_not_called()


class TestTransferQueryResultDownstream:
    """Tests for DBFuncTool.transfer_query_result method."""

    def _make_multi_tool(
        self, source_connector, target_connector, default_db="source_db", scoped_tables=None, agent_config=None
    ):
        """Create a DBFuncTool with mocked _get_connector for multi-db routing."""
        with (
            patch("datus.tools.func_tool.database.SchemaWithValueRAG") as mock_rag,
            patch("datus.tools.func_tool.database.SemanticModelRAG") as mock_sem,
        ):
            mock_rag.return_value.schema_store.table_size.return_value = 0
            mock_sem.return_value.get_size.return_value = 0
            tool = DBFuncTool(source_connector, agent_config=agent_config, scoped_tables=scoped_tables)

        def get_connector(datasource=None):
            if datasource == "target_db":
                return target_connector
            return source_connector

        tool._get_connector = Mock(side_effect=get_connector)
        tool._default_datasource = default_db
        return tool

    def _make_source_connector(self, df):
        """Create a mock source connector that returns a pandas DataFrame."""
        connector = Mock()
        connector.dialect = "duckdb"
        connector.get_databases.return_value = []
        exec_result = Mock()
        exec_result.success = True
        exec_result.sql_return = df
        exec_result.row_count = len(df)
        connector.execute_pandas.return_value = exec_result
        return connector

    def _make_target_connector(self):
        """Create a mock target connector with execute_insert support."""
        connector = Mock()
        connector.dialect = "postgresql"
        connector.get_databases.return_value = []
        ddl_result = Mock(success=True)
        connector.execute_ddl.return_value = ddl_result
        insert_result = Mock(success=True, row_count=0)
        connector.execute_insert.return_value = insert_result
        return (connector, connector.execute_insert)

    def test_transfer_rejects_source_query_outside_scoped_context(self):
        import pandas as pd

        df = pd.DataFrame({"id": [1]})
        source = self._make_source_connector(df)
        source.database_name = "forbidden_db"
        target, _ = self._make_target_connector()
        tool = self._make_multi_tool(source, target, scoped_tables=["allowed_db.orders"])
        result = tool.transfer_query_result(
            source_sql="SELECT * FROM orders",
            source_datasource="source_db",
            target_table="tgt.orders",
            target_datasource="target_db",
            mode="append",
        )
        assert result.success == 0
        assert "outside scoped context" in result.error
        source.execute_query.assert_not_called()
        source.execute_pandas.assert_not_called()
        target.execute_insert.assert_not_called()

    def test_transfer_rejects_target_table_outside_scoped_context(self):
        import pandas as pd

        df = pd.DataFrame({"id": [1]})
        source = self._make_source_connector(df)
        source.dialect = "sqlite"
        source.database_name = "allowed_db"
        target, _ = self._make_target_connector()
        target.dialect = "sqlite"
        target.database_name = "forbidden_db"
        tool = self._make_multi_tool(source, target, scoped_tables=["allowed_db.orders"])
        result = tool.transfer_query_result(
            source_sql="SELECT * FROM orders",
            source_datasource="source_db",
            target_table="orders",
            target_datasource="target_db",
            mode="append",
        )
        assert result.success == 0
        assert "outside scoped context" in result.error
        source.execute_query.assert_not_called()
        source.execute_pandas.assert_not_called()
        target.execute_ddl.assert_not_called()
        target.execute_insert.assert_not_called()

    def test_transfer_rejects_source_query_denied_by_sql_policy(self):
        import pandas as pd

        df = pd.DataFrame({"id": [1]})
        source = self._make_source_connector(df)
        source.database_name = "allowed_db"
        target, _ = self._make_target_connector()
        agent_config = Mock()
        agent_config.active_model.return_value.model = "gpt-5.4"
        agent_config.principal = {"user_id": "analyst"}
        agent_config.sql_policy_config = SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.tools.func_tool.test_database_downstream:DenySqlPolicyEnforcer",
            }
        )
        tool = self._make_multi_tool(source, target, agent_config=agent_config)
        result = tool.transfer_query_result(
            source_sql="SELECT * FROM orders",
            source_datasource="source_db",
            target_table="orders",
            target_datasource="target_db",
            mode="append",
        )
        assert result.success == 0
        assert "transfer source denied" in result.error
        source.execute_query.assert_not_called()
        source.execute_pandas.assert_not_called()
        target.execute_ddl.assert_not_called()
        target.execute_insert.assert_not_called()

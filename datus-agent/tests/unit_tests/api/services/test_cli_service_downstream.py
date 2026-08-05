"""Downstream CLIService datasource, SQL policy, and task-owner coverage."""

import asyncio
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from datus.api.models.base_models import Result
from datus.api.models.cli_models import ExecuteContextInput, ExecuteSQLInput
from datus.api.services.cli_service import CLIService, _SQLTaskRecord
from datus.tools.sql_policy import EnforcementResult, SqlPolicyConfig


class DenyCliSqlPolicyEnforcer:
    def __init__(self, config: SqlPolicyConfig) -> None:
        self.config = config

    def enforce_read(
        self,
        sql: str,
        *,
        datasource: str,
        dialect: str,
        principal: dict | None,
    ) -> EnforcementResult:
        return EnforcementResult(allowed=False, reason="direct SQL policy denied")


class RewriteCliSqlPolicyEnforcer:
    def __init__(self, config: SqlPolicyConfig) -> None:
        self.config = config

    def enforce_read(
        self,
        sql: str,
        *,
        datasource: str,
        dialect: str,
        principal: dict | None,
    ) -> EnforcementResult:
        return EnforcementResult(allowed=True, sql="SELECT 2 AS rewritten", applied_policies=["rewrite"])


class TestCLIServiceExecuteSQL:
    @pytest.mark.asyncio
    async def test_enterprise_read_only_delete_returns_product_copy_without_connector_execution(self, monkeypatch):
        class FakeConnector:
            dialect = "postgresql"

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return=[], row_count=0)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                pass

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={"datasource": "finance"},
            _business_datasource_read_only=True,
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="DELETE FROM users WHERE id = 1", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert result.errorMessage == (
            "企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。"
            "如需删除业务数据，请通过受控的数据维护流程联系管理员。"
        )
        assert connector.executed is False

    @pytest.mark.asyncio
    async def test_execute_sql_json_normalizes_list_rows_with_date_and_decimal(self):
        """JSON responses use a connector-supported format and serialize typed cells."""

        class FakeConnector:
            dialect = "postgresql"

            def execute(self, input_params, result_format):
                assert input_params == {"sql_query": "SELECT nav_date, avg_total_nav FROM fund_nav"}
                assert result_format == "list"
                return SimpleNamespace(
                    success=True,
                    sql_return=[
                        {
                            "nav_date": date(2026, 5, 21),
                            "avg_total_nav": Decimal("0.00"),
                        }
                    ],
                    row_count=1,
                )

        svc = CLIService(agent_config=None, chat_service=None)
        svc.current_db_connector = FakeConnector()
        svc.current_db_name = "fund"

        result = await svc.execute_sql(
            ExecuteSQLInput(
                sql_query="SELECT nav_date, avg_total_nav FROM fund_nav",
                result_format="json",
            )
        )

        assert result.success is True
        assert result.data.result_format == "json"
        assert json.loads(result.data.sql_return) == [
            {
                "nav_date": "2026-05-21",
                "avg_total_nav": "0.00",
            }
        ]

    @pytest.mark.asyncio
    async def test_execute_sql_uses_projected_agent_config(self, monkeypatch):
        """Request-scoped config can route direct SQL without replacing shared task tracking."""

        class FakeConnector:
            dialect = "sqlite"
            catalog_name = "prod"

            def __init__(self):
                self.switch_calls = []

            def switch_context(self, catalog_name, database_name):
                self.switch_calls.append((catalog_name, database_name))

            def execute(self, input_params, result_format):
                assert input_params == {"sql_query": "SELECT 1"}
                assert result_format == "list"
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()
        seen = {}

        class FakeDBManager:
            def __init__(self, datasource_configs):
                seen["datasource_configs"] = datasource_configs
                self.closed = False

            def first_conn_with_name(self, datasource):
                seen["datasource"] = datasource
                return "finance_db", connector

            def close(self):
                seen["closed"] = True
                self.closed = True

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "databases": ["finance_db"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT 1", result_format="json", database_name="finance_db"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is True
        assert seen == {
            "datasource_configs": projected_config.datasource_configs,
            "datasource": "finance",
            "closed": True,
        }
        assert connector.switch_calls == [("prod", "finance_db")]
        assert svc._sql_tasks == {}

    @pytest.mark.asyncio
    async def test_execute_sql_uses_each_projected_config_with_same_datasource_key(self, monkeypatch):
        """Request-scoped direct SQL must not reuse a cached manager for stale configs."""

        class FakeConnector:
            dialect = "sqlite"

            def __init__(self):
                self.executed_sql = []

            def execute(self, input_params, result_format):
                self.executed_sql.append(input_params["sql_query"])
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connectors = {}
        seen_databases = []

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                database = self.datasource_configs[datasource].database
                seen_databases.append(database)
                connector = FakeConnector()
                connectors[database] = connector
                return database, connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)

        def projected_config(database):
            return SimpleNamespace(
                datasource_configs={"finance": SimpleNamespace(database=database)},
                current_datasource="finance",
                principal={
                    "datasource": "finance",
                    "datasource_grants": {"finance": {"effect": "allow", "databases": [database]}},
                },
            )

        svc = CLIService(agent_config=None, chat_service=None)
        result_a = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT 1", result_format="json"),
            user_id="u1",
            agent_config=projected_config("finance_a"),
        )
        result_b = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT 1", result_format="json"),
            user_id="u1",
            agent_config=projected_config("finance_b"),
        )

        assert result_a.success is True
        assert result_b.success is True
        assert seen_databases == ["finance_a", "finance_b"]
        assert set(connectors) == {"finance_a", "finance_b"}

    @pytest.mark.asyncio
    async def test_execute_sql_rejects_ungranted_resolved_default_database(self, monkeypatch):
        """Database grants apply to the resolved default database when request omits it."""

        class FakeConnector:
            dialect = "sqlite"

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "hr", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "databases": ["finance"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT 1", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert result.errorMessage == "Requested database 'hr' is not authorized for datasource 'finance'."
        assert connector.executed is False
        assert svc._sql_tasks == {}

    def test_database_grant_allows_ancestor_of_qualified_table_branch(self):
        """A qualified table leaf keeps its database ancestor usable for direct SQL."""

        projected_config = SimpleNamespace(
            current_datasource="ccks_fund",
            principal={
                "datasource": "ccks_fund",
                "datasource_grants": {
                    "ccks_fund": {
                        "effect": "allow",
                        "databases": ["postgres"],
                        "schemas": ["ccks_fund.test"],
                        "tables": ["ccks_fund.public.mf_benchmarkgrowthrate"],
                    }
                },
            },
        )
        connector = SimpleNamespace(dialect="postgresql")

        assert CLIService._database_grant_denial(projected_config, "ccks_fund", connector) is None
        assert CLIService._database_grant_denial(projected_config, "payroll", connector) is not None

    @pytest.mark.asyncio
    async def test_execute_sql_rejects_ungranted_table_scope(self, monkeypatch):
        """Table-level datasource grants apply before raw direct SQL execution."""

        class FakeConnector:
            dialect = "sqlite"

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "tables": ["allowed_table"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM denied_table", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert "outside scoped context" in result.errorMessage
        assert connector.executed is False

    @pytest.mark.asyncio
    async def test_execute_sql_table_grant_preserves_database_scope(self, monkeypatch):
        """Table grants narrow database grants instead of replacing them."""

        class FakeConnector:
            dialect = "snowflake"
            catalog_name = ""
            database_name = "finance"
            schema_name = "public"

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "databases": ["finance"],
                        "tables": ["orders"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM otherdb.public.orders", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert "outside scoped context" in result.errorMessage
        assert connector.executed is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("dialect", "sql_query"),
        [
            ("postgresql", "SELECT * FROM public.orders"),
            ("oracle", "SELECT * FROM HR.ORDERS"),
            ("sqlserver", "SELECT * FROM dbo.orders"),
            ("mssql", "SELECT * FROM dbo.orders"),
        ],
    )
    async def test_execute_sql_database_grant_allows_schema_qualified_table(
        self,
        monkeypatch,
        dialect,
        sql_query,
    ):
        """Database grants allow schema-qualified SQL inside the active database."""

        class FakeConnector:
            catalog_name = ""
            database_name = "finance"
            schema_name = "public"

            def __init__(self):
                self.dialect = dialect
                self.executed_sql = None

            def execute(self, input_params, result_format):
                self.executed_sql = input_params["sql_query"]
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "databases": ["finance"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query=sql_query, result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is True
        assert connector.executed_sql == sql_query

    @pytest.mark.asyncio
    async def test_execute_sql_starrocks_database_grant_rejects_other_database(self, monkeypatch):
        """StarRocks two-part names are database.table, not schema.table."""

        class FakeConnector:
            dialect = "starrocks"
            catalog_name = "default_catalog"
            database_name = "finance"
            schema_name = ""

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"starrocks_ds": object()},
            current_datasource="starrocks_ds",
            principal={
                "datasource": "starrocks_ds",
                "datasource_grants": {"starrocks_ds": {"effect": "allow", "databases": ["finance"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM public.orders", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert "outside scoped context" in result.errorMessage
        assert connector.executed is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("sql_query", "expected_success"),
        [
            ("SELECT * FROM default_catalog.finance.orders", True),
            ("SELECT * FROM other_catalog.finance.orders", False),
        ],
    )
    async def test_execute_sql_starrocks_catalog_grant_scopes_qualified_table(
        self,
        monkeypatch,
        sql_query,
        expected_success,
    ):
        """StarRocks catalog grants apply to catalog.database.table SQL."""

        class FakeConnector:
            dialect = "starrocks"
            catalog_name = "default_catalog"
            database_name = "finance"
            schema_name = ""

            def __init__(self):
                self.executed_sql = None

            def execute(self, input_params, result_format):
                self.executed_sql = input_params["sql_query"]
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"starrocks_ds": object()},
            current_datasource="starrocks_ds",
            principal={
                "datasource": "starrocks_ds",
                "datasource_grants": {
                    "starrocks_ds": {
                        "effect": "allow",
                        "catalogs": ["default_catalog"],
                        "databases": ["finance"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query=sql_query, result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is expected_success
        if expected_success:
            assert connector.executed_sql == sql_query
        else:
            assert "outside scoped context" in result.errorMessage
            assert connector.executed_sql is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("sql_query", "expected_success"),
        [
            ("SHOW TABLES FROM default_catalog.finance", True),
            ("SHOW TABLES FROM other_catalog.finance", False),
            ("SHOW DATABASES FROM other_catalog", False),
            ("SHOW COLUMNS FROM default_catalog.finance.orders", True),
            ("SHOW COLUMNS FROM other_catalog.finance.orders", False),
            ("SHOW CREATE TABLE default_catalog.finance.orders", True),
            ("SHOW CREATE TABLE other_catalog.finance.orders", False),
            ("SHOW INDEX FROM default_catalog.finance.orders", True),
            ("SHOW INDEX FROM other_catalog.finance.orders", False),
            ("SHOW INDEX FROM orders FROM finance", True),
            ("SHOW INDEX FROM orders FROM other_db", False),
            ("SHOW INDEX FROM default_catalog.finance.orders FROM other_db", False),
            ("SHOW KEYS FROM orders IN other_db", False),
            ("SHOW COLUMNS FROM orders FROM other_db", False),
            ("SHOW TABLES", False),
        ],
    )
    async def test_execute_sql_starrocks_metadata_requires_authorized_scope(
        self,
        monkeypatch,
        sql_query,
        expected_success,
    ):
        """Metadata SQL cannot enumerate outside scoped datasource grants."""

        class FakeConnector:
            dialect = "starrocks"
            catalog_name = "default_catalog"
            database_name = "finance"
            schema_name = ""

            def __init__(self):
                self.executed_sql = None

            def execute(self, input_params, result_format):
                self.executed_sql = input_params["sql_query"]
                return SimpleNamespace(success=True, sql_return="metadata", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"starrocks_ds": object()},
            current_datasource="starrocks_ds",
            principal={
                "datasource": "starrocks_ds",
                "datasource_grants": {
                    "starrocks_ds": {
                        "effect": "allow",
                        "catalogs": ["default_catalog"],
                        "databases": ["finance"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query=sql_query, result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is expected_success
        if expected_success:
            assert connector.executed_sql == sql_query
        else:
            assert "scoped" in result.errorMessage
            assert connector.executed_sql is None

    @pytest.mark.asyncio
    async def test_execute_sql_validates_with_requested_database_context(self, monkeypatch):
        """An explicit database_name is visible to scope validation before execution."""

        class FakeConnector:
            dialect = "postgresql"
            catalog_name = ""
            database_name = "finance_a"
            schema_name = "public"

            def __init__(self):
                self.executed_sql = None
                self.switch_calls = []

            def switch_context(self, catalog_name, database_name):
                self.switch_calls.append((catalog_name, database_name))
                self.database_name = database_name

            def execute(self, input_params, result_format):
                self.executed_sql = input_params["sql_query"]
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_a", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "databases": ["finance_b"]}},
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM orders", result_format="json", database_name="finance_b"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is True
        assert connector.switch_calls == [("", "finance_b")]
        assert connector.executed_sql == "SELECT * FROM orders"

    @pytest.mark.asyncio
    async def test_execute_sql_applies_sql_policy_denial(self, monkeypatch):
        """Direct SQL uses the configured SQL policy before connector execution."""

        class FakeConnector:
            dialect = "sqlite"

            def __init__(self):
                self.executed = False

            def execute(self, input_params, result_format):
                self.executed = True
                return SimpleNamespace(success=True, sql_return="1", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            sql_policy_config=SqlPolicyConfig.from_dict(
                {
                    "enabled": True,
                    "provider": "tests.unit_tests.api.services.test_cli_service_downstream:DenyCliSqlPolicyEnforcer",
                }
            ),
            principal={"datasource": "finance", "datasource_grants": {"finance": {"effect": "allow"}}},
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM allowed_table", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is False
        assert "direct SQL policy denied" in result.errorMessage
        assert connector.executed is False

    @pytest.mark.asyncio
    async def test_execute_sql_applies_sql_policy_rewrite(self, monkeypatch):
        """Direct SQL executes the SQL returned by policy enforcement."""

        class FakeConnector:
            dialect = "sqlite"

            def __init__(self):
                self.executed_sql = None

            def execute(self, input_params, result_format):
                self.executed_sql = input_params["sql_query"]
                return SimpleNamespace(success=True, sql_return="2", row_count=1)

        connector = FakeConnector()

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance", connector

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            sql_policy_config=SqlPolicyConfig.from_dict(
                {
                    "enabled": True,
                    "provider": "tests.unit_tests.api.services.test_cli_service_downstream:RewriteCliSqlPolicyEnforcer",
                }
            ),
            principal={"datasource": "finance", "datasource_grants": {"finance": {"effect": "allow"}}},
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = await svc.execute_sql(
            ExecuteSQLInput(sql_query="SELECT * FROM orders", result_format="json"),
            user_id="u1",
            agent_config=projected_config,
        )

        assert result.success is True
        assert connector.executed_sql == "SELECT 2 AS rewritten"
        assert result.data.sql_query == "SELECT 2 AS rewritten"


class TestCLIServiceStopExecuteSQL:
    @pytest.mark.asyncio
    async def test_stop_running_task_rejects_owner_mismatch(self):
        """A SQL executor user cannot cancel another user's running task."""
        svc = CLIService(agent_config=None, chat_service=None)

        async def _slow_task():
            await asyncio.sleep(60)

        task = asyncio.create_task(_slow_task())
        task_id = "alice-owned-task"
        svc._sql_tasks[task_id] = _SQLTaskRecord(task=task, owner_user_id="alice")

        try:
            stop_result = await svc.stop_execute_sql(task_id, user_id="bob")
            assert stop_result.success is False
            assert stop_result.data.stopped is False
            assert "No running SQL execution" in stop_result.errorMessage
            assert task.cancelled() is False
        finally:
            task.cancel()
            await asyncio.sleep(0)


class TestCLIServiceExecuteContext:
    def test_context_tables_prunes_projected_table_scope(self, monkeypatch):
        """Tables context output must not leak names outside datasource grant scope."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            database_name = "finance_db"
            dialect = "sqlite"
            schema_name = ""

            def get_tables(self):
                return ["orders", "payroll"]

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "tables": ["orders"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_context(
            "tables",
            ExecuteContextInput(context_type="tables"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert [table.table_name for table in result.data.result.tables] == ["orders"]
        assert result.data.result.total_count == 1

    def test_context_catalogs_and_catalog_use_projected_connector_catalog(self, monkeypatch):
        """Catalog context output must use the request-scoped connector catalog."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            schema_name = "finance_schema"

            def get_catalogs(self):
                return ["finance_catalog"]

            def get_tables(self):
                return ["orders"]

        seen = {}

        class FakeDBManager:
            def __init__(self, datasource_configs):
                seen["datasource_configs"] = datasource_configs

            def first_conn_with_name(self, datasource):
                seen["datasource"] = datasource
                return "finance_db", FakeConnector()

            def close(self):
                seen["closed"] = seen.get("closed", 0) + 1

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            db_type="sqlite",
        )
        svc = CLIService(agent_config=None, chat_service=None)
        svc.cli_context.update_database_context(
            catalog="hr_catalog",
            db_name="hr_db",
            schema="hr_schema",
        )

        catalogs_result = svc.execute_context(
            "catalogs",
            ExecuteContextInput(context_type="catalogs"),
            agent_config=projected_config,
        )
        catalog_result = svc.execute_context(
            "catalog",
            ExecuteContextInput(context_type="catalog"),
            agent_config=projected_config,
        )

        assert catalogs_result.success is True
        assert catalogs_result.data.result.context_info["current"] == "finance_catalog"
        assert catalog_result.success is True
        assert catalog_result.data.result.context_info["catalog_name"] == "finance_catalog"
        assert seen == {
            "datasource_configs": projected_config.datasource_configs,
            "datasource": "finance",
            "closed": 2,
        }

    def test_context_catalogs_prunes_projected_catalog_scope(self, monkeypatch):
        """Catalog context output must not leak names outside datasource grant scope."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            schema_name = "finance_schema"

            def get_catalogs(self):
                return ["finance_catalog", "hr_catalog"]

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "catalogs": ["finance_catalog"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_context(
            "catalogs",
            ExecuteContextInput(context_type="catalogs"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.context_info["catalogs"] == ["finance_catalog"]
        assert result.data.result.context_info["total_count"] == 1

    def test_context_catalogs_fallback_respects_projected_catalog_scope(self, monkeypatch):
        """Catalog fallback output must not leak default catalog names outside grant scope."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            schema_name = "finance_schema"

            def get_catalogs(self):
                raise RuntimeError("catalog introspection unavailable")

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "catalogs": ["finance_catalog"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_context(
            "catalogs",
            ExecuteContextInput(context_type="catalogs"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.context_info["catalogs"] == ["finance_catalog"]
        assert result.data.result.context_info["current"] == "finance_catalog"

    def test_context_catalog_counts_projected_table_scope(self, monkeypatch):
        """Catalog context table count must respect datasource grant table scope."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            database_name = "finance_db"
            dialect = "sqlite"
            schema_name = ""

            def get_tables(self):
                return ["orders", "payroll"]

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            db_type="sqlite",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "tables": ["orders"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_context(
            "catalog",
            ExecuteContextInput(context_type="catalog"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.context_info["tables_available"] == 1

    def test_context_context_uses_projected_agent_config_datasource(self, monkeypatch):
        """Request-scoped context output must not leak the shared service datasource."""

        class FakeConnector:
            catalog_name = "finance_catalog"
            db_type = "sqlite"
            database_name = "finance_db"
            schema_name = "finance_schema"

        seen = {}

        class FakeDBManager:
            def __init__(self, datasource_configs):
                seen["datasource_configs"] = datasource_configs

            def first_conn_with_name(self, datasource):
                seen["datasource"] = datasource
                return "finance_db", FakeConnector()

            def close(self):
                seen["closed"] = True

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
        )
        svc = CLIService(agent_config=None, chat_service=None)
        svc.current_datasource = "hr"
        svc.cli_context.update_database_context(
            catalog="hr_catalog",
            db_name="hr_db",
            schema="hr_schema",
        )

        result = svc.execute_context(
            "context",
            ExecuteContextInput(context_type="context"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.context_info["current_datasource"] == "finance"
        assert result.data.result.context_info["current_catalog"] == "finance_catalog"
        assert result.data.result.context_info["current_schema"] == "finance_schema"
        assert seen == {
            "datasource_configs": projected_config.datasource_configs,
            "datasource": "finance",
            "closed": True,
        }


class TestCLIServiceExecuteInternalCommand:
    def test_databases_command_prunes_projected_database_scope(self, monkeypatch):
        """Internal databases output must not leak names outside datasource grant scope."""
        from datus.api.models.cli_models import InternalCommandInput

        class FakeConnector:
            pass

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def get_connections(self, datasource):
                return {
                    "finance_db": FakeConnector(),
                    "payroll_db": FakeConnector(),
                }

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "databases": ["finance_db"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_internal_command(
            "databases",
            InternalCommandInput(command="databases"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.data == {"databases": ["finance_db"]}
        assert result.data.result.command_output == "Available databases: finance_db"

    def test_databases_command_uses_projected_single_connection_database(self, monkeypatch):
        """Internal databases output must use the request-scoped single connector database."""
        from datus.api.models.cli_models import InternalCommandInput

        class FakeConnector:
            database_name = "finance_db"

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def get_connections(self, datasource):
                return FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)
        svc.current_db_name = "shared_hr_db"

        result = svc.execute_internal_command(
            "databases",
            InternalCommandInput(command="databases"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.data == {"databases": ["finance_db"]}
        assert result.data.result.command_output == "Available databases: finance_db"

    def test_tables_command_prunes_projected_table_scope(self, monkeypatch):
        """Internal tables output must not leak names outside datasource grant scope."""
        from datus.api.models.cli_models import InternalCommandInput

        class FakeConnector:
            catalog_name = "finance_catalog"
            database_name = "finance_db"
            dialect = "sqlite"
            schema_name = ""

            def get_tables(self):
                return ["orders", "payroll"]

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "tables": ["orders"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_internal_command(
            "tables",
            InternalCommandInput(command="tables"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.data == {"tables": ["orders"]}
        assert result.data.result.command_output == "Tables: orders"

    def test_schemas_command_prunes_projected_schema_scope(self, monkeypatch):
        """Internal schemas output must not leak names outside datasource grant scope."""
        from datus.api.models.cli_models import InternalCommandInput

        class FakeConnector:
            catalog_name = "finance_catalog"
            database_name = "finance_db"

            def get_schemas(self, catalog_name="", database_name="", include_sys=False):
                return ["mart", "private"]

        class FakeDBManager:
            def __init__(self, datasource_configs):
                self.datasource_configs = datasource_configs

            def first_conn_with_name(self, datasource):
                return "finance_db", FakeConnector()

            def close(self):
                pass

        monkeypatch.setattr("datus.api.services.cli_service.DBManager", FakeDBManager)
        projected_config = SimpleNamespace(
            datasource_configs={"finance": object()},
            current_datasource="finance",
            principal={
                "datasource": "finance",
                "datasource_grants": {
                    "finance": {
                        "effect": "allow",
                        "allow_catalog": True,
                        "schemas": ["mart"],
                    }
                },
            },
        )
        svc = CLIService(agent_config=None, chat_service=None)

        result = svc.execute_internal_command(
            "schemas",
            InternalCommandInput(command="schemas"),
            agent_config=projected_config,
        )

        assert result.success is True
        assert result.data.result.data == {"schemas": ["mart"]}
        assert result.data.result.command_output == "Schemas: mart"

    def test_chat_info_uses_current_user_scope(self):
        """chat_info should read session metadata through ChatService with the current user scope."""
        from datus.api.models.cli_models import InternalCommandInput

        calls = []

        def get_session_info(session_id, user_id=None):
            calls.append((session_id, user_id))
            return Result[dict](
                success=True,
                data={
                    "exists": True,
                    "total_tokens": 9,
                    "action_count": 3,
                    "created_at": "2026-06-28T01:02:03Z",
                    "last_updated": "2026-06-28T01:03:04Z",
                },
            )

        chat_service = SimpleNamespace(get_session_info=get_session_info)
        svc = CLIService(agent_config=None, chat_service=chat_service)
        svc.current_session_id = "session-1"

        result = svc.execute_internal_command("chat_info", InternalCommandInput(command="chat_info"), user_id="alice")

        assert result.success is True
        assert result.data.result.action_taken == "show_chat_info"
        assert result.data.result.data["token_count"] == 9
        assert calls == [("session-1", "alice")]

    def test_sessions_command_formats_chat_session_data(self):
        """sessions command should consume ChatSessionData.sessions, not the model object itself."""
        from datus.api.models.cli_models import (
            ChatSessionData,
            ChatSessionItemInfo,
            InternalCommandInput,
        )

        calls = []

        def list_sessions(user_id=None):
            calls.append(user_id)
            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=[
                        ChatSessionItemInfo(
                            session_id="session-1",
                            created_at="2026-06-28T01:02:03Z",
                            last_updated="2026-06-28T01:03:04Z",
                            total_turns=2,
                            token_count=42,
                        )
                    ],
                    total_count=1,
                ),
            )

        chat_service = SimpleNamespace(list_sessions=list_sessions)
        svc = CLIService(agent_config=None, chat_service=chat_service)

        result = svc.execute_internal_command("sessions", InternalCommandInput(command="sessions"), user_id="alice")

        assert result.success is True
        assert result.data.result.action_taken == "list_sessions"
        assert result.data.result.data == {
            "sessions": [
                {
                    "session_id": "session-1",
                    "created_at": "2026-06-28T01:02:03",
                    "last_updated": "2026-06-28T01:03:04",
                    "total_turns": 2,
                    "token_count": 42,
                    "is_active": False,
                }
            ],
            "total_count": 1,
        }
        assert calls == ["alice"]

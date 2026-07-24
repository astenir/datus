"""
Test cases for DBFuncTool class in datus/tools/tools.py
"""

import json
from unittest.mock import Mock

import pyarrow as pa
import pytest

from datus.tools.db_tools import connector_registry
from datus.tools.func_tool import DBFuncTool

_CONNECTOR_REGISTRY_SNAPSHOT_ATTRS = ("_capabilities", "_uri_builders", "_context_resolvers")


def _snapshot_connector_registry():
    return {
        attr: {k: set(v) if isinstance(v, set) else v for k, v in getattr(connector_registry, attr).items()}
        for attr in _CONNECTOR_REGISTRY_SNAPSHOT_ATTRS
    }


def _restore_connector_registry(snapshots):
    for attr, saved in snapshots.items():
        live = getattr(connector_registry, attr)
        live.clear()
        live.update(saved)


@pytest.fixture(autouse=True)
def _register_test_capabilities():
    """Ensure test dialects have capabilities registered in the registry."""
    snapshots = _snapshot_connector_registry()
    connector_registry.register_handlers("postgresql", capabilities={"database", "schema"})
    connector_registry.register_handlers("snowflake", capabilities={"database", "schema"})
    try:
        yield
    finally:
        _restore_connector_registry(snapshots)


class FakeRecordBatch:
    """Minimal Arrow-like table for select/to_pylist behavior in tests."""

    def __init__(self, rows):
        self._rows = rows

    @property
    def column_names(self):
        return list(self._rows[0]) if self._rows else []

    def select(self, fields):
        selected = [{field: row.get(field) for field in fields} for row in self._rows]
        return FakeRecordBatch(selected)

    def to_pylist(self):
        return list(self._rows)


@pytest.fixture
def mock_connector():
    """Create a mock database connector."""
    connector = Mock()
    connector.dialect = "postgresql"
    connector.catalog_name = ""
    connector.database_name = "db1"
    connector.schema_name = "schema1"
    connector.get_databases.return_value = ["db1", "db2"]
    connector.get_schemas.return_value = ["schema1", "schema2"]
    connector.get_tables.return_value = ["users", "orders"]
    connector.get_views.return_value = ["user_view", "order_view"]
    connector.get_materialized_views.return_value = ["sales_mv"]
    connector.get_schema.return_value = [
        {"name": "id", "type": "integer", "comment": ""},
        {"name": "name", "type": "varchar", "comment": ""},
    ]
    mock_query_result = Mock()
    mock_query_result.success = True
    mock_query_result.sql_return = [{"id": 1, "name": "test"}]
    connector.execute_query.return_value = mock_query_result
    return connector


@pytest.fixture
def db_func_tool(mock_connector):
    """Create a DBFuncTool instance with mocked connector."""
    return DBFuncTool(mock_connector)


@pytest.fixture
def scoped_db_func_tool(mock_connector):
    """Create a DBFuncTool instance with scoped tables."""
    return DBFuncTool(
        mock_connector, scoped_tables={"db1.schema1.orders", "db1.schema1.user_view", "db2.*.orders", "*.schema1.*"}
    )


class TestDBFuncToolDownstream:
    """Test cases for DBFuncTool class."""

    def test_list_databases_respects_projected_role_grant(self, mock_connector):
        """Chat database discovery must use the request's effective role grant."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "databases": ["db1"]}},
            },
        )
        result = tool.list_databases()
        assert result.result == ["db1"]

    def test_list_schemas_respects_projected_role_grant(self, mock_connector):
        """Chat schema discovery must use the request's effective role grant."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "schemas": ["schema1"]}},
            },
        )
        result = tool.list_schemas(database="db1")
        assert result.result == ["schema1"]

    def test_list_namespaces_union_independently_selected_grant_nodes(self, mock_connector):
        """Namespace discovery must union selected database, schema, and table branches."""
        mock_connector.get_databases.return_value = ["ccks_fund", "postgres", "other_db"]
        mock_connector.get_schemas.return_value = ["public", "test", "private"]
        tool = DBFuncTool(
            mock_connector,
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
        databases = tool.list_databases()
        schemas = tool.list_schemas(database="ccks_fund")
        assert databases.result == ["ccks_fund", "postgres"]
        assert schemas.result == ["public", "test"]

    def test_list_tables_respects_projected_role_grant(self, mock_connector):
        """Chat tools must not list tables outside the request's effective role grant."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "schemas": ["schema1"], "tables": ["orders"]}},
            },
        )
        result = tool.list_tables(database="db1", schema_name="schema1", include_views=True)
        assert result.success == 1
        assert result.result == [{"type": "table", "qualified_name": "orders"}]

    def test_list_tables_matches_qualified_role_grant_without_default_schema(self, mock_connector):
        """Qualified UI grants must match bare connector names when no schema was requested."""
        mock_connector.schema_name = ""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "tables": ["db1.schema1.orders"]}},
            },
        )
        result = tool.list_tables(include_views=False)
        assert result.success == 1
        assert result.result == [{"type": "table", "qualified_name": "orders"}]
        wrong_schema = tool.list_tables(schema_name="schema2", include_views=False)
        assert wrong_schema.result == []

    def test_list_tables_unions_qualified_schema_and_table_branches(self, mock_connector):
        """Qualified schema and leaf selections must authorize their independent branches."""
        mock_connector.get_tables.return_value = ["mf_benchmarkgrowthrate", "mf_bondportifoliodetail", "other_table"]
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "ccks_fund",
                "datasource_grants": {
                    "ccks_fund": {
                        "effect": "allow",
                        "schemas": ["ccks_fund.test"],
                        "tables": [
                            "ccks_fund.public.mf_benchmarkgrowthrate",
                            "ccks_fund.public.mf_bondportifoliodetail",
                        ],
                    }
                },
            },
        )
        public_tables = tool.list_tables(
            database="ccks_fund", schema_name="public", datasource="ccks_fund", include_views=False
        )
        test_tables = tool.list_tables(
            database="ccks_fund", schema_name="test", datasource="ccks_fund", include_views=False
        )
        assert public_tables.result == [
            {"type": "table", "qualified_name": "mf_benchmarkgrowthrate"},
            {"type": "table", "qualified_name": "mf_bondportifoliodetail"},
        ]
        assert test_tables.result == [
            {"type": "table", "qualified_name": "mf_benchmarkgrowthrate"},
            {"type": "table", "qualified_name": "mf_bondportifoliodetail"},
            {"type": "table", "qualified_name": "other_table"},
        ]
        private_tables = tool.list_tables(
            database="ccks_fund", schema_name="private", datasource="ccks_fund", include_views=False
        )
        assert private_tables.result == []

    def test_table_detail_uses_same_qualified_leaf_semantics_as_listing(self, mock_connector):
        """Qualified leaf grants must remain reachable through detail while siblings stay denied."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "ccks_fund",
                "datasource_grants": {
                    "ccks_fund": {
                        "effect": "allow",
                        "schemas": ["ccks_fund.test"],
                        "tables": ["ccks_fund.public.mf_benchmarkgrowthrate"],
                    }
                },
            },
        )
        allowed = tool.describe_table(
            "mf_benchmarkgrowthrate", database="ccks_fund", schema_name="public", datasource="ccks_fund"
        )
        denied = tool.describe_table("other_table", database="ccks_fund", schema_name="public", datasource="ccks_fund")
        assert allowed.success == 1
        assert denied.success == 0
        assert "outside the scoped context" in denied.error

    def test_list_tables_keeps_unscoped_admin_grant(self, mock_connector):
        """An allow grant without object scopes keeps the existing full-list behavior."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "allow_catalog": True, "allow_sql": True}},
            },
        )
        result = tool.list_tables(database="db1", schema_name="schema1", include_views=False)
        assert [item["qualified_name"] for item in result.result] == ["users", "orders"]

    def test_list_tables_wildcard_grant_allows_unsupported_schema_dimension(self, mock_connector):
        """A global wildcard must not hide tables when the dialect has no schema coordinate."""
        mock_connector.dialect = "sqlite"
        mock_connector.schema_name = ""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "schemas": ["*"], "tables": ["*"]}},
            },
        )
        result = tool.list_tables(include_views=False)
        assert [item["qualified_name"] for item in result.result] == ["users", "orders"]

    def test_describe_table_rejects_table_outside_projected_role_grant(self, mock_connector):
        """A hidden table must not remain reachable through describe_table."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "tables": ["orders"]}},
            },
        )
        result = tool.describe_table("users", database="db1", schema_name="schema1")
        assert result.success == 0
        assert "outside the scoped context" in result.error
        mock_connector.get_schema.assert_not_called()


class TestDBFuncToolIntegrationDownstream:
    """Integration-style tests for DBFuncTool."""

    def _build_metadata_batch(self):
        return FakeRecordBatch(
            [
                {
                    "catalog_name": "",
                    "database_name": "db1",
                    "schema_name": "public",
                    "table_name": "orders",
                    "table_type": "table",
                    "definition": "CREATE TABLE orders (...);",
                    "identifier": "db1.public.orders",
                    "_distance": 0.05,
                }
            ]
        )

    def _build_sample_batch(self):
        return FakeRecordBatch(
            [
                {
                    "identifier": "db1.public.orders",
                    "table_type": "table",
                    "sample_rows": [{"id": 1, "total": 10}],
                    "_distance": 0.07,
                }
            ]
        )

    def _build_csv_sample_batch(self):
        return FakeRecordBatch(
            [{"identifier": "db1.public.orders", "table_type": "table", "sample_rows": "id,total\n1,10\n"}]
        )

    def _build_metadata_doc_batch(self):
        return FakeRecordBatch(
            [
                {
                    "catalog_name": "",
                    "database_name": "db1",
                    "schema_name": "public",
                    "table_name": "orders",
                    "table_type": "table",
                    "identifier": "db1.public.orders",
                    "title": "db1.public.orders",
                    "payload_json": json.dumps(
                        {
                            "identifier": "db1.public.orders",
                            "catalog_name": "",
                            "database_name": "db1",
                            "schema_name": "public",
                            "table_name": "orders",
                            "table_type": "table",
                        }
                    ),
                    "_score": 3.5,
                }
            ]
        )

    def test_search_table_accepts_results_without_distance(self, db_func_tool):
        """Relational vector backends may omit the optional similarity score."""
        db_func_tool.has_schema = True
        db_func_tool.schema_rag = Mock()
        metadata = self._build_metadata_batch().to_pylist()
        samples = self._build_sample_batch().to_pylist()
        metadata[0].pop("_distance")
        samples[0].pop("_distance")
        db_func_tool.schema_rag.search_similar.return_value = (
            pa.Table.from_pylist(metadata),
            pa.Table.from_pylist(samples),
        )
        result = db_func_tool.search_table("orders table")
        assert result.success == 1
        assert result.result["metadata"][0]["table_name"] == "db1.public.orders"
        assert "_distance" not in result.result["metadata"][0]
        assert result.result["metadata"][0]["sample_rows"] == [{"id": 1, "total": 10}]

    def test_search_table_returns_success_for_empty_arrow_results(self, db_func_tool):
        """An empty semantic search is a valid result even without a distance column."""
        db_func_tool.has_schema = True
        db_func_tool.schema_rag = Mock()
        db_func_tool.schema_rag.search_similar.return_value = (
            pa.table(
                {
                    "catalog_name": pa.array([], type=pa.string()),
                    "database_name": pa.array([], type=pa.string()),
                    "schema_name": pa.array([], type=pa.string()),
                    "table_name": pa.array([], type=pa.string()),
                    "table_type": pa.array([], type=pa.string()),
                    "identifier": pa.array([], type=pa.string()),
                }
            ),
            pa.table(
                {
                    "identifier": pa.array([], type=pa.string()),
                    "table_type": pa.array([], type=pa.string()),
                    "sample_rows": pa.array([], type=pa.string()),
                }
            ),
        )
        result = db_func_tool.search_table("missing table")
        assert result.success == 1
        assert result.result == {"metadata": []}

    def test_search_table_respects_projected_role_grant(self, mock_connector):
        """RAG table discovery must use the same effective grant as list_tables."""
        tool = DBFuncTool(
            mock_connector,
            principal={
                "datasource": "finance",
                "datasource_grants": {"finance": {"effect": "allow", "tables": ["orders"]}},
            },
        )
        tool.has_schema = True
        tool.schema_rag = Mock()
        unauthorized_metadata = {
            **self._build_metadata_batch().to_pylist()[0],
            "table_name": "payroll",
            "identifier": "db1.public.payroll",
        }
        unauthorized_sample = {**self._build_sample_batch().to_pylist()[0], "identifier": "db1.public.payroll"}
        tool.schema_rag.search_similar.return_value = (
            FakeRecordBatch(self._build_metadata_batch().to_pylist() + [unauthorized_metadata]),
            FakeRecordBatch(self._build_sample_batch().to_pylist() + [unauthorized_sample]),
        )
        result = tool.search_table("finance tables")
        assert [row["table_name"] for row in result.result["metadata"]] == ["db1.public.orders"]
        assert result.result["metadata"][0]["sample_rows"] == [{"id": 1, "total": 10}]

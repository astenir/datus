"""Tests for the OceanBase MySQL mode vector backend."""

import os
from unittest.mock import MagicMock

import pandas as pd
import pyarrow as pa
import pymysql
import pytest

from datus_storage_base.backend_config import IsolationType
from datus_storage_base.conditions import eq, like
from datus_storage_base.vector.base import EmbeddingFunction
from datus_storage_oceanbase_mysql.vector.backend import (
    OceanBaseMySQLVectorBackend,
    OceanBaseMySQLVectorDb,
    OceanBaseMySQLVectorTable,
    _compile_where,
    _parse_vector_dim_from_column_type,
    _vector_dim_from_schema,
)
from datus_storage_oceanbase_mysql.vector.schema_converter import schema_to_create_table_sql


class MockEmbeddingFunction(EmbeddingFunction):
    name = "mock"

    def ndims(self):
        return 4

    def generate_embeddings(self, texts, *args, **kwargs):
        vectors = []
        for text in texts:
            if "alpha" in text:
                vectors.append([0.1, 0.2, 0.3, 0.4])
            elif "beta" in text:
                vectors.append([0.2, 0.2, 0.3, 0.4])
            else:
                vectors.append([0.9, 0.1, 0.1, 0.1])
        return vectors


@pytest.fixture(scope="module")
def ob_config():
    host = os.getenv("DATUS_TEST_OB_HOST")
    if not host:
        pytest.skip("Set DATUS_TEST_OB_HOST to run OceanBase MySQL integration tests")
    return {
        "host": host,
        "port": int(os.getenv("DATUS_TEST_OB_PORT", "2881")),
        "user": os.getenv("DATUS_TEST_OB_USER", "root@test"),
        "password": os.getenv("DATUS_TEST_OB_PASSWORD", ""),
        "database": os.getenv("DATUS_TEST_OB_DATABASE", "datus_vector_test"),
        "pool_max_size": 2,
    }


@pytest.fixture
def backend(ob_config):
    _drop_database(ob_config, ob_config["database"])
    _drop_database(ob_config, "datus_vec_project")
    backend = OceanBaseMySQLVectorBackend()
    backend.initialize(ob_config)
    yield backend
    backend.close()


def _drop_database(config, database):
    conn = pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        conn.commit()
    finally:
        conn.close()


def _index_names(table):
    with table._pool.connection(database=table._database_name) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW INDEX FROM {table.table_name}")
            rows = cursor.fetchall()
    return {row.get("Key_name") or row.get("KEY_NAME") for row in rows}


def _schema():
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("description", pa.string()),
            pa.field("category", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("vector", pa.list_(pa.float32(), list_size=4)),
        ]
    )


def test_schema_converter_uses_vector_and_indexable_unique_text():
    sql = schema_to_create_table_sql("db1", "vec_items", _schema(), indexed_columns={"id"})
    assert "`vector` VECTOR(4)" in sql
    assert "`id` VARCHAR(1024) NOT NULL" in sql
    assert "`description` LONGTEXT" in sql
    assert "`tags` LONGTEXT" in sql
    assert "ORGANIZATION HEAP" in sql


def test_ensure_unique_columns_repairs_nullable_existing_key():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [{"cnt": 0}, None]
    schema = _schema().append(pa.field("storage_key", pa.string(), nullable=False))
    table = OceanBaseMySQLVectorTable(
        pool=pool,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
        column_names=list(schema.names),
        schema=schema,
    )
    table._fetch_column_names = lambda: list(schema.names)
    table._fetch_column_definitions = lambda columns: {
        "storage_key": {"COLUMN_TYPE": "longtext", "IS_NULLABLE": "YES"}
    }
    table._unique_index_exists = lambda index_name, expected_columns: False

    table.ensure_unique_columns(["storage_key"])

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any(
        sql == "ALTER TABLE `db1`.`vec_items` MODIFY COLUMN `storage_key` VARCHAR(1024) NOT NULL"
        for sql in executed_sql
    )
    assert any(
        sql == "CREATE UNIQUE INDEX `idx_vec_items_storage_key_uq` ON `db1`.`vec_items` (`storage_key`)"
        for sql in executed_sql
    )


def test_ensure_unique_columns_rejects_duplicate_existing_keys():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [{"cnt": 0}, {"storage_key": "sales:table:orders", "cnt": 2}]
    schema = _schema().append(pa.field("storage_key", pa.string(), nullable=False))
    table = OceanBaseMySQLVectorTable(
        pool=pool,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
        column_names=list(schema.names),
        schema=schema,
    )
    table._fetch_column_names = lambda: list(schema.names)
    table._fetch_column_definitions = lambda columns: {
        "storage_key": {"COLUMN_TYPE": "longtext", "IS_NULLABLE": "YES"}
    }
    table._unique_index_exists = lambda index_name, expected_columns: False

    with pytest.raises(ValueError, match="duplicate row key.*sales:table:orders"):
        table.ensure_unique_columns(["storage_key"])

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any(sql.startswith("ALTER TABLE") for sql in executed_sql)
    assert not any(sql.startswith("CREATE UNIQUE INDEX") for sql in executed_sql)


def test_ensure_unique_columns_is_idempotent_for_conforming_key():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [{"cnt": 0}, None]
    schema = _schema().append(pa.field("storage_key", pa.string(), nullable=False))
    table = OceanBaseMySQLVectorTable(
        pool=pool,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
        column_names=list(schema.names),
        schema=schema,
    )
    table._fetch_column_names = lambda: list(schema.names)
    table._fetch_column_definitions = lambda columns: {
        "storage_key": {"COLUMN_TYPE": "varchar(1024)", "IS_NULLABLE": "NO"}
    }
    table._unique_index_exists = lambda index_name, expected_columns: True

    table.ensure_unique_columns(["storage_key"])

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any(sql.startswith("ALTER TABLE") for sql in executed_sql)
    assert not any(sql.startswith("CREATE UNIQUE INDEX") for sql in executed_sql)


def test_compile_where_uses_mysql_safe_like_escape_literal():
    assert _compile_where(like("name", "active_product_count")) == (r"name LIKE 'active\_product\_count' ESCAPE '\\'")


def test_mysql_migration_expression_translates_sql_concatenation():
    expression = "coalesce(nullif(datasource_id, ''), 'legacy') || ':' || identifier"

    assert OceanBaseMySQLVectorTable._mysql_migration_expression(expression) == (
        "CONCAT(coalesce(nullif(datasource_id, ''), 'legacy'), ':', identifier)"
    )


@pytest.mark.parametrize(
    ("column_type", "expected"),
    [
        ("vector(1024)", 1024),
        ("VECTOR(1536)", 1536),
        (" Vector ( 2048 ) ", 2048),
        ("longtext", None),
    ],
)
def test_parse_vector_dim_from_column_type(column_type, expected):
    assert _parse_vector_dim_from_column_type(column_type) == expected


def test_vector_dim_from_schema_uses_fixed_size_vector_field():
    assert _vector_dim_from_schema(_schema(), "vector") == 4
    assert _vector_dim_from_schema(_schema(), "missing") is None


def test_row_values_serializes_non_vector_lists_without_ambiguous_truth_value():
    metric_schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("base_measures", pa.list_(pa.string())),
            pa.field("dimensions", pa.list_(pa.string())),
            pa.field("entities", pa.list_(pa.string())),
            pa.field("vector", pa.list_(pa.float32(), list_size=4)),
        ]
    )
    table = OceanBaseMySQLVectorTable(
        pool=None,
        database_name="db1",
        table_name="metrics",
        vector_column="vector",
        vector_dim=4,
        column_names=list(metric_schema.names),
        schema=metric_schema,
    )
    row = pd.Series(
        {
            "id": "metric:revenue_rate",
            "base_measures": ["revenue", "orders"],
            "dimensions": ["day", "region"],
            "entities": pd.NA,
            "vector": [0.1, 0.2, 0.3, 0.4],
        }
    )

    values = table._row_values(row, list(metric_schema.names))

    assert values == (
        "metric:revenue_rate",
        '["revenue", "orders"]',
        '["day", "region"]',
        None,
        "[0.1,0.2,0.3,0.4]",
    )


def test_rows_to_arrow_restores_json_list_fields_from_schema():
    table = OceanBaseMySQLVectorTable(
        pool=None,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
        column_names=list(_schema().names),
        schema=_schema(),
    )

    result = table._rows_to_arrow(
        [
            {
                "id": "a",
                "description": '["literal", "text"]',
                "tags": '["daily", "region"]',
                "vector": "[0.1,0.2,0.3,0.4]",
            }
        ],
        select_fields=["id", "description", "tags", "vector"],
    )

    assert result.column("description").to_pylist() == ['["literal", "text"]']
    assert result.column("tags").to_pylist() == [["daily", "region"]]
    assert result.schema.field("tags").type == pa.list_(pa.string())
    assert result.column("vector")[0].as_py() == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_open_table_uses_registered_schema_and_ensures_hnsw_index():
    db = OceanBaseMySQLVectorDb.__new__(OceanBaseMySQLVectorDb)
    db._pool = MagicMock()
    cursor = db._pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"cnt": 0}
    db._database_name = "db1"
    db._isolation = IsolationType.PHYSICAL
    db._logical_namespace = None
    db._table_cache = {}
    db._table_schemas = {}
    db._fetch_column_names = lambda table_name: list(_schema().names)

    db.set_table_schema("vec_items", _schema())
    table = db.open_table(
        "vec_items",
        embedding_function=MockEmbeddingFunction(),
        vector_column="vector",
        source_column="description",
    )

    assert table._schema == _schema()
    assert table.column_names == list(_schema().names)
    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("CREATE VECTOR INDEX `idx_vec_items_vector_hnsw`" in sql for sql in executed_sql)


def test_logical_database_keeps_namespace_for_table_scoping():
    pool = MagicMock()
    db = OceanBaseMySQLVectorDb(
        pool=pool,
        configured_database="db1",
        namespace="project_a",
        isolation=IsolationType.LOGICAL,
    )

    table = db._make_table(
        "vec_items",
        MockEmbeddingFunction(),
        "vector",
        "description",
        4,
        list(_schema().names),
        _schema(),
    )
    scoped = table._inject_namespace_df(pd.DataFrame({"id": ["a"]}))

    assert db._database_name == "db1"
    assert db._logical_namespace == "project_a"
    assert scoped["_datus_namespace"].tolist() == ["project_a"]
    assert table._namespace_where_fragment("`id` = 'a'") == ("`_datus_namespace` = 'project_a' AND (`id` = 'a')")


def test_create_table_automatically_creates_hnsw_index():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"cnt": 0}
    db = OceanBaseMySQLVectorDb(
        pool=pool,
        configured_database="db1",
        namespace="project_a",
        isolation=IsolationType.PHYSICAL,
    )

    db.create_table(
        "vec_items",
        schema=_schema(),
        embedding_function=MockEmbeddingFunction(),
        vector_column="vector",
        source_column="description",
    )

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any(
        "CREATE VECTOR INDEX `idx_vec_items_vector_hnsw` "
        "ON `project_a`.`vec_items`(`vector`) WITH (distance=cosine, type=hnsw, lib=vsag)" in sql
        for sql in executed_sql
    )


def test_create_vector_index_skips_existing_named_index():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"cnt": 1}
    table = OceanBaseMySQLVectorTable(
        pool=pool,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
    )

    table.create_vector_index("vector")

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any(sql.startswith("CREATE VECTOR INDEX") for sql in executed_sql)


def test_create_vector_index_accepts_concurrent_existing_vector_index():
    pool = MagicMock()
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"cnt": 0}
    cursor.execute.side_effect = [
        None,
        pymysql.err.NotSupportedError(1235, "create vector index on column has vector index is not supported"),
    ]
    table = OceanBaseMySQLVectorTable(
        pool=pool,
        database_name="db1",
        table_name="vec_items",
        vector_column="vector",
        vector_dim=4,
    )

    table.create_vector_index("vector")

    pool.connection.return_value.__enter__.return_value.commit.assert_called_once_with()


def test_initialize_requires_connection_config():
    backend = OceanBaseMySQLVectorBackend()
    with pytest.raises(ValueError, match="Missing required OceanBase MySQL config keys"):
        backend.initialize({"host": "127.0.0.1", "port": 2881})


def test_real_oceanbase_vector_crud_search_and_indexes(backend):
    db = backend.connect("datus_vec_project")
    table = db.create_table(
        "vec_items",
        schema=_schema(),
        embedding_function=MockEmbeddingFunction(),
        vector_column="vector",
        source_column="description",
        unique_columns=["id"],
    )
    assert isinstance(table, OceanBaseMySQLVectorTable)
    assert db.table_exists("vec_items")
    assert "idx_vec_items_vector_hnsw" in _index_names(table)

    table.add(
        pd.DataFrame(
            {
                "id": ["a", "b"],
                "description": ["alpha row", "beta row"],
                "category": ["x_value", "y_value"],
                "tags": [["daily", "region"], ["archive"]],
            }
        )
    )
    assert table.count_rows() == 2
    assert table.count_rows(like("category", "x_value")) == 1

    all_rows = table.search_all(select_fields=["id", "category", "tags"], limit=10)
    assert set(all_rows.column("id").to_pylist()) == {"a", "b"}
    tags_by_id = dict(zip(all_rows.column("id").to_pylist(), all_rows.column("tags").to_pylist()))
    assert tags_by_id == {"a": ["daily", "region"], "b": ["archive"]}

    table.merge_insert(
        pd.DataFrame({"id": ["a", "c"], "description": ["alpha changed", "gamma row"], "category": ["z", "z"]}), "id"
    )
    assert table.count_rows() == 3
    assert table.search_all(where=eq("id", "a"), select_fields=["category"]).column("category")[0].as_py() == "z"

    result = table.search_vector("alpha query", "vector", 2, select_fields=["id", "vector"])
    assert result.column("id")[0].as_py() == "a"
    assert result.column("vector")[0].as_py() == pytest.approx([0.1, 0.2, 0.3, 0.4])

    table.create_scalar_index("category")
    table.delete(eq("id", "b"))
    assert table.count_rows() == 2

    db.refresh_table(
        "vec_items", embedding_function=MockEmbeddingFunction(), vector_column="vector", source_column="description"
    )
    assert "vec_items" in db.table_names()


def test_real_oceanbase_vector_logical_isolation(ob_config):
    config = dict(ob_config, isolation="logical")
    backend = OceanBaseMySQLVectorBackend()
    backend.initialize(config)
    try:
        db_a = backend.connect("project_a")
        db_b = backend.connect("project_b")
        table_a = db_a.create_table(
            "logical_vec_items",
            schema=_schema(),
            embedding_function=MockEmbeddingFunction(),
            vector_column="vector",
            source_column="description",
            unique_columns=["id"],
        )
        table_b = db_b.create_table(
            "logical_vec_items",
            schema=_schema(),
            embedding_function=MockEmbeddingFunction(),
            vector_column="vector",
            source_column="description",
            unique_columns=["id"],
        )

        table_a.merge_insert(pd.DataFrame({"id": ["shared"], "description": ["alpha row"], "category": ["a"]}), "id")
        table_b.merge_insert(pd.DataFrame({"id": ["shared"], "description": ["beta row"], "category": ["b"]}), "id")
        table_a.merge_insert(
            pd.DataFrame({"id": ["shared"], "description": ["alpha updated"], "category": ["a2"]}), "id"
        )

        assert table_a.count_rows() == 1
        assert table_b.count_rows() == 1
        assert (
            table_a.search_all(where=eq("id", "shared"), select_fields=["category"]).column("category")[0].as_py()
            == "a2"
        )
        assert (
            table_b.search_all(where=eq("id", "shared"), select_fields=["category"]).column("category")[0].as_py()
            == "b"
        )
    finally:
        backend.close()

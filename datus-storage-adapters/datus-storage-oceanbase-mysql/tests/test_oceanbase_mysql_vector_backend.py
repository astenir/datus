"""Tests for the OceanBase MySQL mode vector backend."""

import os

import pandas as pd
import pyarrow as pa
import pymysql
import pytest

from datus_storage_base.conditions import eq
from datus_storage_base.vector.base import EmbeddingFunction
from datus_storage_oceanbase_mysql.vector.backend import OceanBaseMySQLVectorBackend, OceanBaseMySQLVectorTable
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


def _schema():
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("description", pa.string()),
            pa.field("category", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), list_size=4)),
        ]
    )


def test_schema_converter_uses_vector_and_indexable_unique_text():
    sql = schema_to_create_table_sql("db1", "vec_items", _schema(), indexed_columns={"id"})
    assert "`vector` VECTOR(4)" in sql
    assert "`id` VARCHAR(1024)" in sql
    assert "`description` LONGTEXT" in sql
    assert "ORGANIZATION HEAP" in sql


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

    table.add(pd.DataFrame({"id": ["a", "b"], "description": ["alpha row", "beta row"], "category": ["x", "y"]}))
    assert table.count_rows() == 2

    all_rows = table.search_all(select_fields=["id", "category"], limit=10)
    assert set(all_rows.column("id").to_pylist()) == {"a", "b"}

    table.merge_insert(
        pd.DataFrame({"id": ["a", "c"], "description": ["alpha changed", "gamma row"], "category": ["z", "z"]}), "id"
    )
    assert table.count_rows() == 3
    assert table.search_all(where=eq("id", "a"), select_fields=["category"]).column("category")[0].as_py() == "z"

    result = table.search_vector("alpha query", "vector", 2, select_fields=["id", "vector"])
    assert result.column("id")[0].as_py() == "a"
    assert result.column("vector")[0].as_py() == pytest.approx([0.1, 0.2, 0.3, 0.4])

    table.create_vector_index("vector")
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

        assert table_a.count_rows() == 1
        assert table_b.count_rows() == 1
        assert (
            table_a.search_all(where=eq("id", "shared"), select_fields=["category"]).column("category")[0].as_py()
            == "a"
        )
        assert (
            table_b.search_all(where=eq("id", "shared"), select_fields=["category"]).column("category")[0].as_py()
            == "b"
        )
    finally:
        backend.close()

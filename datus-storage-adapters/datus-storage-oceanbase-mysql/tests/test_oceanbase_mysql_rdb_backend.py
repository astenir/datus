"""Tests for the OceanBase MySQL mode RDB backend."""

from dataclasses import dataclass
from typing import Optional

import pymysql
import pytest

from datus_storage_base.backend_config import LOGICAL_NAMESPACE_COLUMN
from datus_storage_base.rdb.base import ColumnDef, IndexDef, TableDefinition, UniqueViolationError, WhereOp
from datus_storage_oceanbase_mysql.rdb.backend import (
    OceanBaseMySQLRdbBackend,
    OceanBaseMySQLRdbDatabase,
    OceanBaseMySQLRdbTable,
)


@dataclass
class Item:
    id: Optional[int] = None
    name: Optional[str] = None
    value: Optional[str] = None
    score: Optional[int] = None


@dataclass
class KeyedItem:
    key_col: Optional[str] = None
    value: Optional[str] = None


def _table_def() -> TableDefinition:
    return TableDefinition(
        table_name="test_items",
        columns=[
            ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
            ColumnDef(name="name", col_type="TEXT", nullable=False),
            ColumnDef(name="value", col_type="TEXT"),
            ColumnDef(name="score", col_type="INTEGER", default=0),
        ],
        indices=[IndexDef(name="idx_test_items_name", columns=["name"], unique=True)],
    )


def _keyed_table_def() -> TableDefinition:
    return TableDefinition(
        table_name="keyed_items",
        columns=[
            ColumnDef(name="key_col", col_type="TEXT", nullable=False, unique=True),
            ColumnDef(name="value", col_type="TEXT"),
        ],
    )


def _default_text_table_def() -> TableDefinition:
    return TableDefinition(
        table_name="default_text_items",
        columns=[
            ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
            ColumnDef(name="lookup_key", col_type="TEXT", default="", unique=True),
            ColumnDef(name="body", col_type="TEXT", default=""),
            ColumnDef(name="status", col_type="TEXT", default="running"),
        ],
    )


class TestBackendConfig:
    def test_initialize_requires_connection_config(self):
        backend = OceanBaseMySQLRdbBackend()
        with pytest.raises(ValueError, match="Missing required OceanBase MySQL config keys"):
            backend.initialize({"host": "127.0.0.1", "port": 2881})

    def test_physical_database_name_uses_namespace_and_store(self, monkeypatch):
        backend = OceanBaseMySQLRdbBackend()
        backend.initialize({"host": "127.0.0.1", "port": 2881, "user": "root@test", "password": "", "database": "base"})
        monkeypatch.setattr(OceanBaseMySQLRdbDatabase, "_ensure_database", lambda self: None)

        class DummyPool:
            def connection(self, database=None):
                raise AssertionError("database creation is covered by integration tests")

        backend._pool = DummyPool()
        db = backend.connect("project", "subject_tree")
        assert db.database_name == "project__subject_tree"


class TestLogicalDdl:
    def test_logical_table_definition_scopes_unique_columns(self, monkeypatch):
        backend = OceanBaseMySQLRdbBackend()
        backend.initialize(
            {
                "host": "127.0.0.1",
                "port": 2881,
                "user": "root@test",
                "password": "",
                "database": "datus_storage",
                "isolation": "logical",
            }
        )
        executed = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def execute(self, sql, params=None):
                executed.append(sql)

        class Conn:
            open = True

            def cursor(self):
                return Cursor()

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        class Pool:
            def connection(self, database=None):
                class CM:
                    def __enter__(self):
                        return Conn()

                    def __exit__(self, *args):
                        return None

                return CM()

        monkeypatch.setattr(backend, "_pool", Pool())
        db = backend.connect("project_a", "store_a")
        table = db.ensure_table(_keyed_table_def())

        assert isinstance(table, OceanBaseMySQLRdbTable)
        joined = "\n".join(executed)
        assert LOGICAL_NAMESPACE_COLUMN in joined
        assert "UNIQUE INDEX" in joined
        assert "`key_col`, `_datus_namespace`" in joined
        assert "`key_col` VARCHAR(1024) NOT NULL" in joined
        assert "`value` LONGTEXT" in joined

    def test_longtext_columns_do_not_emit_defaults(self, monkeypatch):
        backend = OceanBaseMySQLRdbBackend()
        backend.initialize(
            {
                "host": "127.0.0.1",
                "port": 2881,
                "user": "root@test",
                "password": "",
                "database": "datus_storage",
                "isolation": "logical",
            }
        )
        monkeypatch.setattr(OceanBaseMySQLRdbDatabase, "_ensure_database", lambda self: None)
        db = backend.connect("project_a", "store_a")

        joined = "\n".join(db._generate_ddl(_default_text_table_def()))
        assert "`lookup_key` VARCHAR(1024) UNIQUE DEFAULT ''" in joined
        assert "`body` LONGTEXT DEFAULT" not in joined
        assert "`status` LONGTEXT DEFAULT" not in joined


@pytest.fixture(scope="module")
def ob_config():
    import os

    host = os.getenv("DATUS_TEST_OB_HOST")
    if not host:
        pytest.skip("Set DATUS_TEST_OB_HOST to run OceanBase MySQL integration tests")
    return {
        "host": host,
        "port": int(os.getenv("DATUS_TEST_OB_PORT", "2881")),
        "user": os.getenv("DATUS_TEST_OB_USER", "root@test"),
        "password": os.getenv("DATUS_TEST_OB_PASSWORD", ""),
        "database": os.getenv("DATUS_TEST_OB_DATABASE", "datus_storage_test"),
        "pool_max_size": 2,
    }


@pytest.fixture
def backend(ob_config):
    _drop_database(ob_config, ob_config["database"])
    _drop_database(ob_config, "datus_ob_test__rdb")
    backend = OceanBaseMySQLRdbBackend()
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


def test_real_oceanbase_physical_crud(backend):
    db = backend.connect("datus_ob_test", "rdb")
    table = db.ensure_table(_table_def())
    row_id = table.insert(Item(name="alpha", value="one", score=1))
    assert row_id > 0

    assert table.query(Item, where={"name": "alpha"}) == [Item(id=row_id, name="alpha", value="one", score=1)]
    assert table.update({"value": "two"}, where=[("name", WhereOp.EQ, "alpha")]) == 1
    assert table.query(Item, where={"name": "alpha"})[0].value == "two"

    with pytest.raises(UniqueViolationError):
        table.insert(Item(name="alpha", value="dup"))

    assert table.delete(where={"name": "alpha"}) == 1


def test_real_oceanbase_logical_isolation(ob_config):
    config = dict(ob_config, isolation="logical")
    backend = OceanBaseMySQLRdbBackend()
    backend.initialize(config)
    try:
        db_a = backend.connect("project_a", "logical")
        db_b = backend.connect("project_b", "logical")
        table_a = db_a.ensure_table(_keyed_table_def())
        table_b = db_b.ensure_table(_keyed_table_def())

        table_a.upsert(KeyedItem(key_col="shared", value="a"), conflict_columns=["key_col"])
        table_b.upsert(KeyedItem(key_col="shared", value="b"), conflict_columns=["key_col"])

        assert table_a.query(KeyedItem, where={"key_col": "shared"}) == [KeyedItem(key_col="shared", value="a")]
        assert table_b.query(KeyedItem, where={"key_col": "shared"}) == [KeyedItem(key_col="shared", value="b")]
    finally:
        backend.close()

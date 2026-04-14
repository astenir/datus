"""Tests for PostgresRdbBackend (three-layer architecture)."""

from dataclasses import dataclass
from typing import Optional

import pytest
from psycopg_pool import PoolClosed

from datus_storage_base.rdb.base import (
    ColumnDef,
    IndexDef,
    IntegrityError,
    TableDefinition,
    WhereOp,
)
from datus_storage_postgresql.rdb.backend import PgRdbDatabase, PgRdbTable, PostgresRdbBackend


@dataclass
class TestItem:
    """Dataclass for testing CRUD operations."""

    id: Optional[int] = None
    name: Optional[str] = None
    value: Optional[str] = None
    score: Optional[int] = None


@dataclass
class UpsertRecord:
    """Dataclass for testing upsert operations."""

    key_col: Optional[str] = None
    data: Optional[str] = None


@dataclass
class TypedRecord:
    """Dataclass for testing various column types."""

    id: Optional[int] = None
    name: Optional[str] = None
    score: Optional[float] = None
    active: Optional[bool] = None


@pytest.fixture
def backend(pg_config):
    """Create and initialize a PostgresRdbBackend."""
    b = PostgresRdbBackend()
    b.initialize(pg_config)
    yield b
    b.close()


@pytest.fixture
def db(backend):
    """Connect and return a PgRdbDatabase handle."""
    d = backend.connect(namespace="", store_db_name="test")
    yield d
    # Clean up all tables to prevent cross-test data leaks
    try:
        with d.get_connection() as conn:
            rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
            for row in rows:
                tbl = row["tablename"] if isinstance(row, dict) else row[0]
                conn.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
            conn.commit()
    except Exception:
        pass


@pytest.fixture
def test_table_def():
    """A simple table definition for testing."""
    return TableDefinition(
        table_name="test_items",
        columns=[
            ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
            ColumnDef(name="name", col_type="TEXT", nullable=False),
            ColumnDef(name="value", col_type="TEXT"),
            ColumnDef(name="score", col_type="INTEGER", default=0),
        ],
        indices=[
            IndexDef(name="idx_test_items_name", columns=["name"], unique=True),
        ],
    )


# ==============================================================================
# Backend lifecycle tests
# ==============================================================================


class TestBackendLifecycle:
    def test_initialize_missing_all_keys(self):
        b = PostgresRdbBackend()
        with pytest.raises(ValueError, match="Missing required"):
            b.initialize({})

    def test_initialize_missing_partial_keys(self):
        b = PostgresRdbBackend()
        with pytest.raises(ValueError, match="password, dbname"):
            b.initialize({"host": "localhost", "port": 5432, "user": "pg"})

    def test_connect_returns_database(self, db):
        assert isinstance(db, PgRdbDatabase)
        assert db.pool is not None

    def test_connect_multiple_stores(self, backend):
        db1 = backend.connect(namespace="", store_db_name="store_a")
        db2 = backend.connect(namespace="", store_db_name="store_b")
        assert db1 is not db2
        # Multiple stores share the same connection pool
        assert db1.pool is db2.pool

    def test_close_releases_all(self, pg_config):
        b = PostgresRdbBackend()
        b.initialize(pg_config)
        db1 = b.connect(namespace="", store_db_name="c1")
        db2 = b.connect(namespace="", store_db_name="c2")
        b.close()
        with pytest.raises(PoolClosed):
            with db1.get_connection():
                pass
        with pytest.raises(PoolClosed):
            with db2.get_connection():
                pass

    def test_dialect(self, db):
        assert db.dialect == "postgresql"

    def test_param_placeholder(self, db):
        assert db.param_placeholder() == "%s"


# ==============================================================================
# ensure_table() tests
# ==============================================================================


class TestEnsureTable:
    def test_returns_pg_rdb_table(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        assert isinstance(table, PgRdbTable)
        assert table.table_name == "test_items"

    def test_table_exists_in_pg(self, db, test_table_def):
        db.ensure_table(test_table_def)
        with db.get_connection() as conn:
            rows = db.execute_query(
                conn,
                "SELECT table_name FROM information_schema.tables WHERE table_name = %s",
                ("test_items",),
            )
            assert len(rows) == 1

    def test_idempotent(self, db, test_table_def):
        t1 = db.ensure_table(test_table_def)
        t2 = db.ensure_table(test_table_def)
        assert isinstance(t1, PgRdbTable)
        assert isinstance(t2, PgRdbTable)

    def test_with_indices(self, db, test_table_def):
        """Unique index on 'name' should be created."""
        db.ensure_table(test_table_def)
        with db.get_connection() as conn:
            rows = db.execute_query(
                conn,
                "SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexname = %s",
                ("test_items", "idx_test_items_name"),
            )
            assert len(rows) == 1

    def test_with_constraints(self, db):
        table_def = TableDefinition(
            table_name="constrained_tbl",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="a", col_type="INTEGER"),
                ColumnDef(name="b", col_type="INTEGER"),
            ],
            constraints=["CHECK (a > 0)"],
        )
        table = db.ensure_table(table_def)
        assert isinstance(table, PgRdbTable)

    def test_column_type_mapping(self, db):
        """BLOB -> BYTEA, REAL -> REAL, BOOLEAN -> BOOLEAN."""
        table_def = TableDefinition(
            table_name="type_map_tbl",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="data", col_type="BLOB"),
                ColumnDef(name="score", col_type="REAL"),
                ColumnDef(name="active", col_type="BOOLEAN"),
                ColumnDef(name="ts", col_type="TIMESTAMP"),
            ],
        )
        db.ensure_table(table_def)
        with db.get_connection() as conn:
            rows = db.execute_query(
                conn,
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                ("type_map_tbl",),
            )
            type_map = {r["column_name"]: r["data_type"] for r in rows}
            assert type_map["data"] == "bytea"
            assert type_map["score"] == "real"
            assert type_map["active"] == "boolean"
            assert "timestamp" in type_map["ts"]


# ==============================================================================
# insert() tests
# ==============================================================================


class TestInsert:
    def test_basic(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        row_id = table.insert(TestItem(name="item1", value="val1", score=10))
        assert row_id is not None
        assert row_id > 0

    def test_sequential_ids(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        id1 = table.insert(TestItem(name="a", value="v1"))
        id2 = table.insert(TestItem(name="b", value="v2"))
        assert id2 > id1

    def test_duplicate_unique_raises_integrity_error(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="dup", value="v1"))
        with pytest.raises(IntegrityError):
            table.insert(TestItem(name="dup", value="v2"))

    def test_none_fields_excluded(self, db, test_table_def):
        """Fields with None are excluded from INSERT, using DB defaults."""
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="no_score"))
        results = table.query(TestItem, where={"name": "no_score"})
        assert len(results) == 1
        # score should use DB default (0)
        assert results[0].score == 0


# ==============================================================================
# query() tests
# ==============================================================================


class TestQuery:
    def test_all_rows(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="q1", value="v1", score=10))
        table.insert(TestItem(name="q2", value="v2", score=20))
        results = table.query(TestItem)
        assert len(results) == 2
        assert all(isinstance(r, TestItem) for r in results)

    def test_empty_table(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        results = table.query(TestItem)
        assert results == []

    def test_where_dict(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="w1", value="v1", score=10))
        table.insert(TestItem(name="w2", value="v2", score=20))
        results = table.query(TestItem, where={"name": "w1"})
        assert len(results) == 1
        assert results[0].name == "w1"

    def test_where_tuples_ge(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="t1", value="v1", score=10))
        table.insert(TestItem(name="t2", value="v2", score=20))
        table.insert(TestItem(name="t3", value="v3", score=30))
        results = table.query(TestItem, where=[("score", WhereOp.GE, 20)])
        assert len(results) == 2

    def test_where_tuples_lt(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="lt1", value="v1", score=10))
        table.insert(TestItem(name="lt2", value="v2", score=20))
        results = table.query(TestItem, where=[("score", WhereOp.LT, 20)])
        assert len(results) == 1
        assert results[0].name == "lt1"

    def test_where_tuples_ne(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="ne1", value="v1", score=10))
        table.insert(TestItem(name="ne2", value="v2", score=20))
        results = table.query(TestItem, where=[("score", WhereOp.NE, 10)])
        assert len(results) == 1
        assert results[0].name == "ne2"

    def test_where_multiple_conditions(self, db, test_table_def):
        """Multiple WHERE conditions combined with AND."""
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="mc1", value="a", score=10))
        table.insert(TestItem(name="mc2", value="a", score=20))
        table.insert(TestItem(name="mc3", value="b", score=10))
        results = table.query(
            TestItem,
            where=[("value", WhereOp.EQ, "a"), ("score", WhereOp.GT, 10)],
        )
        assert len(results) == 1
        assert results[0].name == "mc2"

    def test_where_is_null(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="null1", value=None, score=10))
        table.insert(TestItem(name="null2", value="v2", score=20))
        results = table.query(TestItem, where=[("value", WhereOp.IS_NULL, None)])
        assert len(results) == 1
        assert results[0].name == "null1"

    def test_where_is_not_null(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="nn1", value=None, score=10))
        table.insert(TestItem(name="nn2", value="v2", score=20))
        results = table.query(TestItem, where=[("value", WhereOp.IS_NOT_NULL, None)])
        assert len(results) == 1
        assert results[0].name == "nn2"

    def test_select_columns(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="c1", value="v1", score=10))
        results = table.query(TestItem, columns=["name", "score"])
        assert len(results) == 1
        assert results[0].name == "c1"
        assert results[0].score == 10

    def test_order_by_asc(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="o1", value="v1", score=30))
        table.insert(TestItem(name="o2", value="v2", score=10))
        table.insert(TestItem(name="o3", value="v3", score=20))
        results = table.query(TestItem, order_by=["score"])
        assert [r.score for r in results] == [10, 20, 30]

    def test_order_by_desc(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="d1", value="v1", score=30))
        table.insert(TestItem(name="d2", value="v2", score=10))
        table.insert(TestItem(name="d3", value="v3", score=20))
        results = table.query(TestItem, order_by=["-score"])
        assert [r.score for r in results] == [30, 20, 10]


# ==============================================================================
# update() tests
# ==============================================================================


class TestUpdate:
    def test_single_row(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="up1", value="old", score=10))
        count = table.update({"value": "new"}, where={"name": "up1"})
        assert count == 1
        results = table.query(TestItem, where={"name": "up1"})
        assert results[0].value == "new"

    def test_multiple_rows(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="m1", value="old", score=10))
        table.insert(TestItem(name="m2", value="old", score=10))
        table.insert(TestItem(name="m3", value="keep", score=20))
        count = table.update({"value": "updated"}, where=[("score", WhereOp.EQ, 10)])
        assert count == 2

    def test_empty_data(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        count = table.update({})
        assert count == 0

    def test_no_where_updates_all(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="all1", value="old"))
        table.insert(TestItem(name="all2", value="old"))
        count = table.update({"value": "new"})
        assert count == 2

    def test_update_unique_violation_raises(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="uv1", value="v1"))
        table.insert(TestItem(name="uv2", value="v2"))
        with pytest.raises(IntegrityError):
            table.update({"name": "uv1"}, where={"name": "uv2"})


# ==============================================================================
# delete() tests
# ==============================================================================


class TestDelete:
    def test_with_where(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="d1", value="v1"))
        table.insert(TestItem(name="d2", value="v2"))
        count = table.delete(where={"name": "d1"})
        assert count == 1
        assert len(table.query(TestItem)) == 1

    def test_all(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="da1", value="v1"))
        table.insert(TestItem(name="da2", value="v2"))
        count = table.delete()
        assert count == 2
        assert len(table.query(TestItem)) == 0

    def test_no_match(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="nm1", value="v1"))
        count = table.delete(where={"name": "nonexistent"})
        assert count == 0
        assert len(table.query(TestItem)) == 1


# ==============================================================================
# upsert() tests
# ==============================================================================


class TestUpsert:
    def test_insert_new(self, db):
        table_def = TableDefinition(
            table_name="upsert_new",
            columns=[
                ColumnDef(name="key_col", col_type="TEXT", primary_key=True),
                ColumnDef(name="data", col_type="TEXT"),
            ],
        )
        table = db.ensure_table(table_def)
        table.upsert(UpsertRecord(key_col="k1", data="d1"), ["key_col"])
        results = table.query(UpsertRecord)
        assert len(results) == 1
        assert results[0].data == "d1"

    def test_update_on_conflict(self, db):
        table_def = TableDefinition(
            table_name="upsert_conflict",
            columns=[
                ColumnDef(name="key_col", col_type="TEXT", primary_key=True),
                ColumnDef(name="data", col_type="TEXT"),
            ],
        )
        table = db.ensure_table(table_def)
        table.upsert(UpsertRecord(key_col="k1", data="original"), ["key_col"])
        table.upsert(UpsertRecord(key_col="k1", data="updated"), ["key_col"])
        results = table.query(UpsertRecord, where={"key_col": "k1"})
        assert len(results) == 1
        assert results[0].data == "updated"

    def test_do_nothing_when_all_columns_are_conflict(self, db):
        """When all columns are conflict columns, should DO NOTHING."""
        table_def = TableDefinition(
            table_name="upsert_nothing",
            columns=[
                ColumnDef(name="key_col", col_type="TEXT", primary_key=True),
            ],
        )
        table = db.ensure_table(table_def)

        @dataclass
        class KeyOnly:
            key_col: Optional[str] = None

        table.upsert(KeyOnly(key_col="k1"), ["key_col"])
        table.upsert(KeyOnly(key_col="k1"), ["key_col"])  # should not raise
        results = table.query(KeyOnly)
        assert len(results) == 1


# ==============================================================================
# transaction() tests
# ==============================================================================


class TestTransaction:
    def test_commit(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        with db.transaction():
            table.insert(TestItem(name="tx1", value="v1"))
            table.insert(TestItem(name="tx2", value="v2"))
        assert len(table.query(TestItem)) == 2

    def test_rollback(self, db, test_table_def):
        table = db.ensure_table(test_table_def)
        with pytest.raises(ValueError):
            with db.transaction():
                table.insert(TestItem(name="txr1", value="v1"))
                raise ValueError("intentional")
        assert len(table.query(TestItem)) == 0

    def test_mixed_operations(self, db, test_table_def):
        """Insert + update + delete in a single transaction."""
        table = db.ensure_table(test_table_def)
        table.insert(TestItem(name="pre", value="before"))

        with db.transaction():
            table.insert(TestItem(name="tx_new", value="v1"))
            table.update({"value": "after"}, where={"name": "pre"})

        results = table.query(TestItem, order_by=["name"])
        assert len(results) == 2
        pre = [r for r in results if r.name == "pre"][0]
        assert pre.value == "after"


# ==============================================================================
# Namespace (schema) isolation tests
# ==============================================================================


class TestNamespace:
    def test_creates_schema(self, backend):
        db = backend.connect(namespace="test_ns_rdb", store_db_name="test")
        table_def = TableDefinition(
            table_name="ns_tbl",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="name", col_type="TEXT"),
            ],
        )
        table = db.ensure_table(table_def)
        assert table.table_name == "test_ns_rdb.ns_tbl"

    def test_crud_in_namespace(self, backend):
        db = backend.connect(namespace="crud_ns", store_db_name="test")
        table_def = TableDefinition(
            table_name="crud_tbl",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="name", col_type="TEXT"),
            ],
        )
        table = db.ensure_table(table_def)
        row_id = table.insert(TestItem(name="ns_item"))
        assert row_id > 0

        results = table.query(TestItem)
        assert len(results) == 1
        assert results[0].name == "ns_item"

    def test_isolation_between_namespaces(self, backend):
        """Tables in different namespaces are independent."""
        db_a = backend.connect(namespace="ns_a", store_db_name="test")
        db_b = backend.connect(namespace="ns_b", store_db_name="test")

        table_def = TableDefinition(
            table_name="shared_name",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="name", col_type="TEXT"),
            ],
        )
        tbl_a = db_a.ensure_table(table_def)
        tbl_b = db_b.ensure_table(table_def)

        tbl_a.insert(TestItem(name="from_a"))
        tbl_b.insert(TestItem(name="from_b1"))
        tbl_b.insert(TestItem(name="from_b2"))

        assert len(tbl_a.query(TestItem)) == 1
        assert len(tbl_b.query(TestItem)) == 2

    def test_public_namespace(self, backend):
        """Empty namespace uses 'public' schema — no prefix."""
        db = backend.connect(namespace="", store_db_name="test")
        table_def = TableDefinition(
            table_name="pub_tbl",
            columns=[
                ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
                ColumnDef(name="name", col_type="TEXT"),
            ],
        )
        table = db.ensure_table(table_def)
        assert table.table_name == "pub_tbl"  # no schema prefix


# ==============================================================================
# Convenience method tests
# ==============================================================================


class TestConvenienceMethods:
    def test_execute_and_query(self, db, test_table_def):
        db.ensure_table(test_table_def)
        with db.get_connection() as conn:
            db.execute(
                conn,
                "INSERT INTO test_items (name, value, score) VALUES (%s, %s, %s)",
                ("item1", "val1", 10),
            )
            conn.commit()
            rows = db.execute_query(
                conn,
                "SELECT name, value, score FROM test_items WHERE name = %s",
                ("item1",),
            )
            assert len(rows) == 1
            assert rows[0]["name"] == "item1"
            assert rows[0]["score"] == 10

    def test_execute_insert_returns_id(self, db, test_table_def):
        db.ensure_table(test_table_def)
        with db.get_connection() as conn:
            row_id = db.execute_insert(
                conn,
                "INSERT INTO test_items (name, value) VALUES (%s, %s) RETURNING id",
                ("ret1", "val"),
            )
            conn.commit()
            assert row_id > 0

    def test_execute_multiple_rows(self, db, test_table_def):
        db.ensure_table(test_table_def)
        with db.get_connection() as conn:
            for i in range(5):
                db.execute(
                    conn,
                    "INSERT INTO test_items (name, value, score) VALUES (%s, %s, %s)",
                    (f"multi_{i}", f"v_{i}", i * 10),
                )
            conn.commit()
            rows = db.execute_query(
                conn,
                "SELECT * FROM test_items WHERE name LIKE %s ORDER BY score",
                ("multi_%",),
            )
            assert len(rows) == 5
            assert rows[0]["score"] == 0
            assert rows[4]["score"] == 40

    def test_pool_reuse(self, db, test_table_def):
        db.ensure_table(test_table_def)
        with db.get_connection() as conn1:
            db.execute(conn1, "INSERT INTO test_items (name, value) VALUES (%s, %s)", ("p1", "v1"))
            conn1.commit()
        with db.get_connection() as conn2:
            rows = db.execute_query(conn2, "SELECT name FROM test_items WHERE name = %s", ("p1",))
            assert len(rows) == 1


# ==============================================================================
# Logical isolation tests
# ==============================================================================


@pytest.fixture
def logical_backend(pg_config):
    """Create a PostgresRdbBackend with logical isolation."""
    config = {**pg_config, "isolation": "logical"}
    b = PostgresRdbBackend()
    b.initialize(config)
    yield b
    b.close()


@pytest.fixture
def logical_db(logical_backend):
    """Connect with a namespace under logical isolation."""
    return logical_backend.connect(namespace="tenant_a", store_db_name="test")


@pytest.fixture
def logical_test_table_def():
    """A table definition for logical isolation testing (separate from physical tests)."""
    return TableDefinition(
        table_name="logical_test_items",
        columns=[
            ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
            ColumnDef(name="name", col_type="TEXT", nullable=False),
            ColumnDef(name="value", col_type="TEXT"),
            ColumnDef(name="score", col_type="INTEGER", default=0),
        ],
        indices=[
            IndexDef(name="idx_logical_test_items_name", columns=["name"], unique=True),
        ],
    )


@pytest.fixture
def logical_table(logical_db, logical_test_table_def):
    """Create table and clean data for logical isolation tests."""
    table = logical_db.ensure_table(logical_test_table_def)
    # Clean any leftover data from previous tests
    with logical_db.get_connection() as conn:
        conn.execute("DELETE FROM logical_test_items")
        conn.commit()
    return table


class TestLogicalIsolation:
    def test_table_in_public_schema(self, logical_db, logical_test_table_def):
        """Logical isolation uses public schema, not namespace as schema."""
        table = logical_db.ensure_table(logical_test_table_def)
        assert table.table_name == "logical_test_items"  # no schema prefix

    def test_datasource_id_column_created(self, logical_db, logical_test_table_def):
        """ensure_table auto-adds datasource_id column."""
        logical_db.ensure_table(logical_test_table_def)
        with logical_db.get_connection() as conn:
            rows = logical_db.execute_query(
                conn,
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                ("logical_test_items", "datasource_id"),
            )
            assert len(rows) == 1

    def test_datasource_id_index_created(self, logical_db, logical_test_table_def):
        """ensure_table auto-creates B-tree index on datasource_id."""
        logical_db.ensure_table(logical_test_table_def)
        with logical_db.get_connection() as conn:
            rows = logical_db.execute_query(
                conn,
                "SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexname LIKE %s",
                ("logical_test_items", "%datasource_id%"),
            )
            assert len(rows) >= 1

    def test_insert_injects_datasource_id(self, logical_db, logical_table):
        """Insert auto-injects datasource_id = namespace."""
        logical_table.insert(TestItem(name="li1", value="v1"))
        with logical_db.get_connection() as conn:
            rows = logical_db.execute_query(
                conn,
                "SELECT datasource_id FROM logical_test_items WHERE name = %s",
                ("li1",),
            )
            assert rows[0]["datasource_id"] == "tenant_a"

    def test_query_filters_by_datasource_id(self, logical_backend, logical_test_table_def):
        """Query only returns rows for the connected namespace."""
        db_a = logical_backend.connect(namespace="tenant_a", store_db_name="test")
        db_b = logical_backend.connect(namespace="tenant_b", store_db_name="test")

        tbl_a = db_a.ensure_table(logical_test_table_def)
        tbl_b = db_b.ensure_table(logical_test_table_def)

        # Clean slate
        with db_a.get_connection() as conn:
            conn.execute("DELETE FROM logical_test_items")
            conn.commit()

        tbl_a.insert(TestItem(name="a1", value="from_a"))
        tbl_b.insert(TestItem(name="b1", value="from_b"))
        tbl_b.insert(TestItem(name="b2", value="from_b"))

        assert len(tbl_a.query(TestItem)) == 1
        assert len(tbl_b.query(TestItem)) == 2

    def test_update_scoped_to_datasource(self, logical_backend, logical_test_table_def):
        """Update only affects rows for the connected namespace."""
        db_a = logical_backend.connect(namespace="tenant_a", store_db_name="test")
        db_b = logical_backend.connect(namespace="tenant_b", store_db_name="test")

        tbl_a = db_a.ensure_table(logical_test_table_def)
        tbl_b = db_b.ensure_table(logical_test_table_def)

        # Clean slate
        with db_a.get_connection() as conn:
            conn.execute("DELETE FROM logical_test_items")
            conn.commit()

        tbl_a.insert(TestItem(name="ua1", value="old"))
        tbl_b.insert(TestItem(name="ub1", value="old"))

        count = tbl_a.update({"value": "new"})
        assert count == 1
        assert tbl_a.query(TestItem)[0].value == "new"
        assert tbl_b.query(TestItem)[0].value == "old"

    def test_delete_scoped_to_datasource(self, logical_backend, logical_test_table_def):
        """Delete only affects rows for the connected namespace."""
        db_a = logical_backend.connect(namespace="tenant_a", store_db_name="test")
        db_b = logical_backend.connect(namespace="tenant_b", store_db_name="test")

        tbl_a = db_a.ensure_table(logical_test_table_def)
        tbl_b = db_b.ensure_table(logical_test_table_def)

        # Clean slate
        with db_a.get_connection() as conn:
            conn.execute("DELETE FROM logical_test_items")
            conn.commit()

        tbl_a.insert(TestItem(name="da1", value="v"))
        tbl_b.insert(TestItem(name="db1", value="v"))

        tbl_a.delete()
        assert len(tbl_a.query(TestItem)) == 0
        assert len(tbl_b.query(TestItem)) == 1

    def test_upsert_injects_datasource_id(self, logical_db):
        """Upsert auto-injects datasource_id."""
        table_def = TableDefinition(
            table_name="logical_upsert",
            columns=[
                ColumnDef(name="key_col", col_type="TEXT", primary_key=True),
                ColumnDef(name="data", col_type="TEXT"),
            ],
        )
        table = logical_db.ensure_table(table_def)
        table.upsert(UpsertRecord(key_col="k1", data="d1"), ["key_col"])
        results = table.query(UpsertRecord)
        assert len(results) == 1
        assert results[0].data == "d1"

    def test_query_result_excludes_datasource_id(self, logical_table):
        """Query results should not include datasource_id in model fields."""
        logical_table.insert(TestItem(name="excl1", value="v1"))
        results = logical_table.query(TestItem)
        assert len(results) == 1
        # TestItem has fields: id, name, value, score — no datasource_id
        assert isinstance(results[0], TestItem)

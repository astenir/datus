"""Tests for PgvectorBackend (three-layer architecture)."""

import pandas as pd
import pyarrow as pa
import pytest
from conftest import MockEmbeddingFunction
from psycopg_pool import PoolClosed

from datus_storage_base.conditions import and_, eq, not_, or_
from datus_storage_postgresql.vector.backend import PgvectorBackend, PgVectorDb, PgVectorTable


@pytest.fixture
def backend(pg_config):
    """Create a PgvectorBackend instance with connection config."""
    b = PgvectorBackend()
    b.initialize(pg_config)
    yield b
    b.close()


@pytest.fixture
def db(backend):
    """Connect to the test database and return a VectorDatabase handle."""
    return backend.connect("")


@pytest.fixture
def test_schema():
    """A simple PyArrow schema for testing."""
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("description", pa.string()),
            pa.field("category", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), list_size=4)),
        ]
    )


@pytest.fixture
def embedding_function():
    """Mock embedding function."""
    return MockEmbeddingFunction()


@pytest.fixture
def table(db, test_schema, embedding_function):
    """Create a test table and return the VectorTable handle."""
    db.drop_table("test_vectors", ignore_missing=True)
    tbl = db.create_table(
        "test_vectors",
        schema=test_schema,
        embedding_function=embedding_function,
        vector_column="vector",
        source_column="description",
    )
    with db.pool.connection() as conn:
        conn.execute(f"ALTER TABLE {tbl.table_name} ADD CONSTRAINT uq_test_vectors_id UNIQUE (id)")
        conn.commit()
    return tbl


def _sample_df(ids, descriptions=None, categories=None):
    """Helper to build a DataFrame for tests."""
    n = len(ids)
    return pd.DataFrame(
        {
            "id": ids,
            "description": descriptions or [f"desc {i}" for i in range(n)],
            "category": categories or ["cat"] * n,
        }
    )


# ==============================================================================
# Backend lifecycle tests
# ==============================================================================


class TestBackendLifecycle:
    def test_initialize_stores_config(self, pg_config):
        b = PgvectorBackend()
        b.initialize(pg_config)
        assert b._config == pg_config

    def test_connect_missing_config(self):
        b = PgvectorBackend()
        b.initialize({})
        with pytest.raises(ValueError, match="Missing required"):
            b.connect("test")

    def test_connect_returns_pg_vector_db(self, db):
        assert isinstance(db, PgVectorDb)
        assert db.pool is not None

    def test_connect_multiple(self, backend):
        db1 = backend.connect("multi_ns_1")
        db2 = backend.connect("multi_ns_2")
        assert db1 is not db2

    def test_close(self, pg_config):
        b = PgvectorBackend()
        b.initialize(pg_config)
        db = b.connect("")
        b.close()
        with pytest.raises(PoolClosed):
            with db.pool.connection():
                pass


# ==============================================================================
# Database-level tests (PgVectorDb)
# ==============================================================================


class TestPgVectorDb:
    def test_table_exists(self, db, table):
        assert db.table_exists("test_vectors")
        assert not db.table_exists("nonexistent_table")

    def test_table_names(self, db, table):
        names = db.table_names()
        assert "test_vectors" in names

    def test_table_names_limit(self, db, test_schema, embedding_function):
        for i in range(3):
            db.drop_table(f"tn_limit_{i}", ignore_missing=True)
            db.create_table(f"tn_limit_{i}", schema=test_schema, embedding_function=embedding_function)
        names = db.table_names(limit=2)
        assert len(names) <= 2

    def test_create_table(self, db, test_schema, embedding_function):
        db.drop_table("ct_test", ignore_missing=True)
        tbl = db.create_table("ct_test", schema=test_schema, embedding_function=embedding_function)
        assert isinstance(tbl, PgVectorTable)
        assert tbl.vector_dim == 4
        assert db.table_exists("ct_test")

    def test_create_table_no_schema_no_exist_ok_raises(self, db):
        with pytest.raises(ValueError, match="Schema is required"):
            db.create_table("fail_tbl", schema=None, exist_ok=False)

    def test_create_table_unsupported_schema_raises(self, db):
        with pytest.raises(TypeError, match="Unsupported schema type"):
            db.create_table("fail_tbl2", schema={"bad": "schema"})

    def test_open_table_cached(self, db, table, embedding_function):
        """open_table returns the cached handle if available."""
        opened = db.open_table("test_vectors", embedding_function=embedding_function)
        assert opened is table

    def test_open_table_uncached(self, db, test_schema, embedding_function):
        """open_table for uncached table reads columns from information_schema."""
        db.drop_table("open_uc", ignore_missing=True)
        db.create_table("open_uc", schema=test_schema, embedding_function=embedding_function)
        # Clear cache to force re-read
        db._table_cache.pop("open_uc", None)
        opened = db.open_table("open_uc")
        assert isinstance(opened, PgVectorTable)
        assert "id" in opened.column_names

    def test_drop_table(self, db, test_schema, embedding_function):
        db.drop_table("drop_me", ignore_missing=True)
        db.create_table("drop_me", schema=test_schema, embedding_function=embedding_function)
        assert db.table_exists("drop_me")
        db.drop_table("drop_me")
        assert not db.table_exists("drop_me")

    def test_drop_table_ignore_missing(self, db):
        db.drop_table("no_such_table_xyz", ignore_missing=True)

    def test_drop_table_missing_raises(self, db):
        from psycopg.errors import UndefinedTable

        with pytest.raises(UndefinedTable):
            db.drop_table("no_such_table_xyz", ignore_missing=False)

    def test_refresh_table(self, db, table):
        """refresh_table re-opens the table."""
        refreshed = db.refresh_table("test_vectors")
        assert isinstance(refreshed, PgVectorTable)


# ==============================================================================
# Write operations (PgVectorTable)
# ==============================================================================


class TestVectorTableWrite:
    def test_add(self, table):
        table.add(_sample_df(["1", "2", "3"]))
        assert table.count_rows() == 3

    def test_add_empty(self, table):
        table.add(pd.DataFrame({"id": [], "description": [], "category": []}))
        assert table.count_rows() == 0

    def test_add_with_precomputed_vectors(self, table):
        """When vector column is already filled, skip embedding computation."""
        df = pd.DataFrame(
            {
                "id": ["pv1"],
                "description": ["precomp"],
                "category": ["c"],
                "vector": [[0.5, 0.5, 0.5, 0.5]],
            }
        )
        table.add(df)
        assert table.count_rows() == 1

    def test_merge_insert(self, table):
        table.add(_sample_df(["u1", "u2"]))
        update_df = pd.DataFrame(
            {
                "id": ["u1", "u3"],
                "description": ["updated_u1", "new_u3"],
                "category": ["updated", "new"],
            }
        )
        table.merge_insert(update_df, "id")
        assert table.count_rows() == 3
        result = table.search_all(where=eq("id", "u1"))
        assert result.column("category")[0].as_py() == "updated"

    def test_delete_str(self, table):
        table.add(_sample_df(["d1", "d2", "d3"], categories=["rm", "keep", "rm"]))
        table.delete("category = 'rm'")
        assert table.count_rows() == 1

    def test_delete_where_expr(self, table):
        table.add(_sample_df(["de1", "de2", "de3"], categories=["rm", "keep", "rm"]))
        table.delete(eq("category", "rm"))
        assert table.count_rows() == 1

    def test_update(self, table):
        table.add(_sample_df(["up1", "up2"], categories=["old", "old"]))
        table.update(eq("id", "up1"), {"category": "new"})
        result = table.search_all(where=eq("id", "up1"))
        assert result.column("category")[0].as_py() == "new"

    def test_update_no_where(self, table):
        table.add(_sample_df(["uw1", "uw2"], categories=["old", "old"]))
        table.update(None, {"category": "all_new"})
        result = table.search_all()
        assert all(v.as_py() == "all_new" for v in result.column("category"))


# ==============================================================================
# Search operations (PgVectorTable)
# ==============================================================================


class TestVectorTableSearch:
    def test_search_vector(self, table):
        table.add(_sample_df(["s1", "s2", "s3"]))
        results = table.search_vector(query_text="test", vector_column="vector", top_n=2)
        assert results.num_rows == 2

    def test_search_vector_with_where_str(self, table):
        table.add(_sample_df(["w1", "w2", "w3"], categories=["alpha", "beta", "alpha"]))
        results = table.search_vector(
            query_text="test",
            vector_column="vector",
            top_n=10,
            where="category = 'alpha'",
        )
        assert results.num_rows == 2

    def test_search_vector_with_where_expr(self, table):
        table.add(_sample_df(["we1", "we2", "we3"], categories=["alpha", "beta", "alpha"]))
        results = table.search_vector(
            query_text="test",
            vector_column="vector",
            top_n=10,
            where=eq("category", "alpha"),
        )
        assert results.num_rows == 2

    def test_search_vector_with_select_fields(self, table):
        table.add(_sample_df(["sel1"]))
        results = table.search_vector(
            query_text="test",
            vector_column="vector",
            top_n=1,
            select_fields=["id", "category"],
        )
        assert results.num_rows == 1
        assert "id" in results.column_names
        assert "description" not in results.column_names

    def test_search_vector_no_embedding_fn_raises(self, db, test_schema):
        """Table without embedding_function cannot do vector search."""
        db.drop_table("no_emb", ignore_missing=True)
        tbl = db.create_table("no_emb", schema=test_schema)
        with pytest.raises(RuntimeError, match="No embedding function"):
            tbl.search_vector(query_text="test", vector_column="vector", top_n=1)

    def test_search_hybrid_fallback(self, table):
        table.add(_sample_df(["h1"]))
        results = table.search_hybrid(
            query_text="test",
            vector_source_column="description",
            top_n=1,
        )
        assert results.num_rows == 1

    def test_search_all(self, table):
        table.add(_sample_df(["a1", "a2"]))
        results = table.search_all()
        assert results.num_rows == 2

    def test_search_all_with_where_str(self, table):
        table.add(_sample_df(["f1", "f2", "f3"], categories=["keep", "drop", "keep"]))
        results = table.search_all(where="category = 'keep'")
        assert results.num_rows == 2

    def test_search_all_with_where_expr(self, table):
        table.add(_sample_df(["fe1", "fe2", "fe3"], categories=["keep", "drop", "keep"]))
        results = table.search_all(where=eq("category", "keep"))
        assert results.num_rows == 2

    def test_search_all_with_and(self, table):
        table.add(_sample_df(["ae1", "ae2", "ae3"], categories=["keep", "keep", "drop"]))
        results = table.search_all(where=and_(eq("category", "keep"), eq("id", "ae1")))
        assert results.num_rows == 1

    def test_search_all_with_or(self, table):
        table.add(_sample_df(["or1", "or2", "or3"], categories=["a", "b", "c"]))
        results = table.search_all(where=or_(eq("category", "a"), eq("category", "c")))
        assert results.num_rows == 2

    def test_search_all_with_not(self, table):
        table.add(_sample_df(["nt1", "nt2", "nt3"], categories=["keep", "drop", "keep"]))
        results = table.search_all(where=not_(eq("category", "drop")))
        assert results.num_rows == 2

    def test_search_all_with_limit(self, table):
        table.add(_sample_df([f"lim{i}" for i in range(5)]))
        results = table.search_all(limit=3)
        assert results.num_rows == 3

    def test_search_all_no_limit(self, table):
        table.add(_sample_df([f"nl{i}" for i in range(5)]))
        results = table.search_all(limit=None)
        assert results.num_rows == 5

    def test_search_all_with_select_fields(self, table):
        table.add(_sample_df(["sf1"]))
        results = table.search_all(select_fields=["id", "category"])
        assert results.num_rows == 1
        assert "id" in results.column_names
        assert "description" not in results.column_names

    def test_empty_table(self, table):
        assert table.count_rows() == 0
        results = table.search_all()
        assert results.num_rows == 0


# ==============================================================================
# count_rows() tests
# ==============================================================================


class TestCountRows:
    def test_count_no_filter(self, table):
        table.add(_sample_df(["c1", "c2", "c3"]))
        assert table.count_rows() == 3

    def test_count_with_where_str(self, table):
        table.add(_sample_df(["cs1", "cs2", "cs3"], categories=["p", "q", "p"]))
        assert table.count_rows(where="category = 'p'") == 2

    def test_count_with_where_expr(self, table):
        table.add(_sample_df(["ce1", "ce2", "ce3"], categories=["p", "q", "p"]))
        assert table.count_rows(where=eq("category", "p")) == 2

    def test_count_empty(self, table):
        assert table.count_rows() == 0


# ==============================================================================
# Index operations tests
# ==============================================================================


class TestIndexOperations:
    def test_vector_index_cosine(self, table):
        table.add(_sample_df([f"vi{i}" for i in range(10)]))
        table.create_vector_index("vector", metric="cosine")

    def test_vector_index_l2(self, table):
        table.add(_sample_df([f"vl{i}" for i in range(10)]))
        table.create_vector_index("vector", metric="l2")

    def test_vector_index_ip(self, table):
        table.add(_sample_df([f"vp{i}" for i in range(10)]))
        table.create_vector_index("vector", metric="ip")

    def test_scalar_index(self, table):
        table.create_scalar_index("category")

    def test_fts_index_single_field(self, table):
        table.create_fts_index("description")

    def test_fts_index_multiple_fields(self, table):
        table.create_fts_index(["description", "category"])


# ==============================================================================
# Namespace (schema) isolation tests
# ==============================================================================


class TestVectorNamespace:
    def test_namespace_creates_schema(self, backend):
        db = backend.connect("vec_ns_test")
        assert db.namespace == "vec_ns_test"

    def test_namespace_qualified_table_name(self, backend, test_schema, embedding_function):
        db = backend.connect("qn_ns")
        db.drop_table("ns_tbl", ignore_missing=True)
        tbl = db.create_table("ns_tbl", schema=test_schema, embedding_function=embedding_function)
        assert tbl.table_name == "qn_ns.ns_tbl"

    def test_namespace_isolation(self, backend, test_schema, embedding_function):
        """Tables in different namespaces are independent."""
        db_a = backend.connect("iso_a")
        db_b = backend.connect("iso_b")

        db_a.drop_table("shared", ignore_missing=True)
        db_b.drop_table("shared", ignore_missing=True)

        tbl_a = db_a.create_table("shared", schema=test_schema, embedding_function=embedding_function)
        tbl_b = db_b.create_table("shared", schema=test_schema, embedding_function=embedding_function)

        tbl_a.add(_sample_df(["a1"]))
        tbl_b.add(_sample_df(["b1", "b2"]))

        assert tbl_a.count_rows() == 1
        assert tbl_b.count_rows() == 2

    def test_public_namespace(self, db):
        """Empty namespace uses 'public' — no schema prefix."""
        assert db.namespace == ""


# ==============================================================================
# Arrow conversion tests
# ==============================================================================


class TestArrowConversion:
    def test_rows_to_arrow_types(self, table):
        """Verify returned PyArrow table has correct types."""
        table.add(_sample_df(["ar1", "ar2"]))
        result = table.search_all()
        assert isinstance(result, pa.Table)
        assert result.num_rows == 2
        assert result.column("id").type == pa.string()

    def test_empty_result_with_select_fields(self, table):
        result = table.search_all(select_fields=["id", "category"])
        assert result.num_rows == 0
        assert "id" in result.column_names
        assert "category" in result.column_names


# ==============================================================================
# Vector logical isolation tests
# ==============================================================================


@pytest.fixture
def logical_backend(pg_config):
    """Create a PgvectorBackend with logical isolation."""
    config = {**pg_config, "isolation": "logical"}
    b = PgvectorBackend()
    b.initialize(config)
    yield b
    b.close()


@pytest.fixture
def logical_db(logical_backend):
    """Connect with a namespace under logical isolation."""
    return logical_backend.connect("tenant_a")


def _drop_table_raw(pool, table_name):
    """Drop a table directly via pool, bypassing logical isolation guard (test-only)."""
    with pool.connection() as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


@pytest.fixture
def logical_table(logical_db, test_schema, embedding_function):
    """Create a test table under logical isolation."""
    _drop_table_raw(logical_db.pool, "logical_vectors")
    tbl = logical_db.create_table(
        "logical_vectors",
        schema=test_schema,
        embedding_function=embedding_function,
        vector_column="vector",
        source_column="description",
    )
    return tbl


class TestVectorLogicalIsolation:
    def test_table_in_public_schema(self, logical_table):
        """Logical isolation uses public schema."""
        assert "." not in logical_table.table_name  # no schema prefix

    def test_datasource_id_column_created(self, logical_db, logical_table):
        """create_table auto-adds datasource_id column."""
        with logical_db.pool.connection() as conn:
            rows = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                ("logical_vectors", "datasource_id"),
            ).fetchall()
            assert len(rows) == 1

    def test_add_injects_datasource_id(self, logical_db, logical_table):
        """add() auto-injects datasource_id."""
        logical_table.add(_sample_df(["la1"]))
        with logical_db.pool.connection() as conn:
            rows = conn.execute("SELECT datasource_id FROM logical_vectors WHERE id = 'la1'").fetchall()
            val = rows[0]["datasource_id"] if isinstance(rows[0], dict) else rows[0][0]
            assert val == "tenant_a"

    def test_search_all_filters_by_datasource(self, logical_backend, test_schema, embedding_function):
        """search_all only returns rows for the connected namespace."""
        db_a = logical_backend.connect("tenant_a")
        db_b = logical_backend.connect("tenant_b")

        _drop_table_raw(db_a.pool, "shared_vec")
        tbl_a = db_a.create_table("shared_vec", schema=test_schema, embedding_function=embedding_function)
        tbl_b = db_b.open_table("shared_vec", embedding_function=embedding_function)

        tbl_a.add(_sample_df(["a1"]))
        tbl_b.add(_sample_df(["b1", "b2"]))

        assert tbl_a.count_rows() == 1
        assert tbl_b.count_rows() == 2

    def test_delete_scoped_to_datasource(self, logical_backend, test_schema, embedding_function):
        """delete() only affects rows for the connected namespace."""
        db_a = logical_backend.connect("tenant_a")
        db_b = logical_backend.connect("tenant_b")

        _drop_table_raw(db_a.pool, "del_vec")
        tbl_a = db_a.create_table("del_vec", schema=test_schema, embedding_function=embedding_function)
        tbl_b = db_b.open_table("del_vec", embedding_function=embedding_function)

        tbl_a.add(_sample_df(["da1"]))
        tbl_b.add(_sample_df(["db1"]))

        tbl_a.delete(eq("id", "da1"))
        assert tbl_a.count_rows() == 0
        assert tbl_b.count_rows() == 1

    def test_update_scoped_to_datasource(self, logical_backend, test_schema, embedding_function):
        """update() only affects rows for the connected namespace."""
        db_a = logical_backend.connect("tenant_a")
        db_b = logical_backend.connect("tenant_b")

        _drop_table_raw(db_a.pool, "upd_vec")
        tbl_a = db_a.create_table("upd_vec", schema=test_schema, embedding_function=embedding_function)
        tbl_b = db_b.open_table("upd_vec", embedding_function=embedding_function)

        tbl_a.add(_sample_df(["ua1"], categories=["old"]))
        tbl_b.add(_sample_df(["ub1"], categories=["old"]))

        tbl_a.update(eq("id", "ua1"), {"category": "new"})
        result_a = tbl_a.search_all()
        result_b = tbl_b.search_all()
        assert result_a.column("category")[0].as_py() == "new"
        assert result_b.column("category")[0].as_py() == "old"

    def test_search_all_excludes_datasource_id_from_results(self, logical_table):
        """Default SELECT should not include datasource_id column."""
        logical_table.add(_sample_df(["ex1"]))
        result = logical_table.search_all()
        assert "datasource_id" not in result.column_names

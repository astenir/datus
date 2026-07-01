# datus-storage-postgresql

PostgreSQL storage adapter for [datus-agent](https://github.com/Datus-ai/Datus-agent). Provides both RDB and Vector backends powered by a single PostgreSQL instance.

## Backends

### RDB Backend — `PostgresRdbBackend`

Implements `BaseRdbBackend` using psycopg v3 and psycopg-pool with a three-layer architecture:

- **`PostgresRdbBackend`** (lifecycle): `initialize()`, `connect(namespace, store_db_name)`, `close()`
- **`PgRdbDatabase`** (database-level, implements `RdbDatabase`): `ensure_table()`, `transaction()`, `close()`
- **`PgRdbTable`** (table-level, implements `RdbTable`): `insert()`, `query()`, `update()`, `delete()`, `upsert()`

Features:
- Full CRUD via `PgRdbTable` (no need to pass table name)
- `upsert()` with PostgreSQL `ON CONFLICT` (dataclass record input)
- `transaction()` context manager with auto-commit/rollback
- Namespace-based data isolation via PostgreSQL schemas
- Connection pooling with configurable min/max size
- Convenience methods on `PgRdbDatabase`: `get_connection()`, `execute()`, `execute_query()`, `execute_insert()`

### Vector Backend — `PgvectorBackend`

Implements `BaseVectorBackend` using the [pgvector](https://github.com/pgvector/pgvector) extension with a three-layer architecture:

- **`PgvectorBackend`** (lifecycle): `initialize()`, `connect(namespace)`, `build_embedding_config()`, `close()`
- **`PgVectorDb`** (database-level, implements `VectorDatabase`): `table_exists()`, `table_names()`, `create_table()`, `open_table()`, `drop_table()`
- **`PgVectorTable`** (table-level, implements `VectorTable`): `add()`, `merge_insert()`, `delete()`, `update()`, `search_vector()`, `search_hybrid()`, `search_all()`, `count_rows()`, index operations

Features:
- `WhereExpr` support (condition AST nodes or `None`) via `build_where()`
- Vector similarity search (cosine / L2 / inner product)
- Automatic embedding computation on insert
- HNSW vector index, B-tree scalar index, GIN full-text index
- PyArrow Schema to PostgreSQL DDL mapping

## Configuration

Both backends register as `type: postgresql` and accept the same configuration parameters. They can point to the same PostgreSQL instance.

```yaml
storage:
  rdb:
    type: postgresql
    host: localhost
    port: 5432
    user: postgres
    password: postgres
    dbname: datus
    pool_min_size: 1
    pool_max_size: 10
  vector:
    type: postgresql
    host: localhost
    port: 5432
    user: postgres
    password: postgres
    dbname: datus
    pool_min_size: 1
    pool_max_size: 10
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `host` | Yes | — | Database host |
| `port` | Yes | — | Database port |
| `user` | Yes | — | Username |
| `password` | Yes | — | Password |
| `dbname` | Yes | — | Database name |
| `pool_min_size` | No | `1` | Minimum connections in pool |
| `pool_max_size` | No | `10` | Maximum connections in pool |

The vector backend automatically enables the pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector`) on connect.

## Usage

### RDB Backend

```python
from dataclasses import dataclass
from datus.storage.rdb.base import TableDefinition, ColumnDef

@dataclass
class User:
    id: int = None
    name: str = None
    email: str = None

backend = PostgresRdbBackend()
backend.initialize(config)

# connect() returns a RdbDatabase handle (namespace maps to PG schema)
db = backend.connect(namespace="my_app", store_db_name="user_store")

# ensure_table() returns a RdbTable handle
users_table = db.ensure_table(TableDefinition(
    table_name="users",
    columns=[
        ColumnDef(name="id", col_type="INTEGER", primary_key=True, autoincrement=True),
        ColumnDef(name="name", col_type="TEXT"),
        ColumnDef(name="email", col_type="TEXT"),
    ],
))

# Table-level CRUD (no need to pass table name)
row_id = users_table.insert(User(name="Alice", email="alice@example.com"))
users = users_table.query(User, where={"name": "Alice"})
users_table.update({"email": "new@example.com"}, where={"name": "Alice"})
users_table.delete(where={"name": "Alice"})

# Transaction on database level
with db.transaction():
    users_table.insert(User(name="Bob", email="bob@example.com"))
    users_table.insert(User(name="Carol", email="carol@example.com"))
```

### Vector Backend

```python
from datus.storage.conditions import eq, and_

backend = PgvectorBackend()
backend.initialize(config)

# connect() returns a VectorDatabase handle
db = backend.connect(namespace="my_namespace")

# create_table() / open_table() return VectorTable handles
table = db.create_table("my_table", schema=my_schema, embedding_function=emb_config)
table = db.open_table("my_table")

# Table-level operations (no handle passing)
table.add(df)
results = table.search_all(where=eq("category", "active"))
results = table.search_all(where=and_(eq("status", "active"), eq("type", "A")))
results = table.search_vector(query_text="hello", vector_column="vector", top_n=10)

# Database-level operations
db.drop_table("my_table", ignore_missing=True)
assert db.table_exists("my_table") == False
```

## Entry Points

```toml
[project.entry-points."datus.storage.rdb"]
postgresql = "datus_storage_postgresql.rdb:register"

[project.entry-points."datus.storage.vector"]
postgresql = "datus_storage_postgresql.vector:register"
```

Once installed, datus-agent discovers and registers both backends automatically — no manual wiring needed.

## Source Layout

```text
datus_storage_postgresql/
├── rdb/
│   ├── __init__.py          # register() → RdbRegistry
│   └── backend.py           # PostgresRdbBackend
└── vector/
    ├── __init__.py           # register() → VectorRegistry
    ├── backend.py            # PgvectorBackend
    └── schema_converter.py   # PyArrow Schema → PostgreSQL DDL
```

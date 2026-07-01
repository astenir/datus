# datus-storage-adapter

Pluggable storage backend adapters for [datus-agent](https://github.com/Datus-ai/Datus-agent). This monorepo provides database-specific implementations of `BaseRdbBackend` and `BaseVectorBackend`, discovered automatically via setuptools entry-points.

## Project Structure

```
datus-storage-adapter/
├── pyproject.toml                  # uv workspace root
└── datus-storage-postgresql/       # PostgreSQL adapter package
    ├── pyproject.toml
    ├── datus_storage_postgresql/
    │   ├── rdb/                    # Relational database backend
    │   └── vector/                 # Vector database backend (pgvector)
    └── tests/
```

## Available Adapters

| Adapter | Type | Documentation |
|---------|------|---------------|
| [datus-storage-postgresql](datus-storage-postgresql/README.md) | `postgresql` | RDB + Vector backends for PostgreSQL |

## Development

### Setup

```bash
uv sync --all-packages --all-extras
```

### Running Tests

Tests require Docker (testcontainers starts a `pgvector/pgvector:pg17` container):

```bash
# Install local datus-agent (PyPI version may lack latest interfaces)
uv pip install -e ../Datus-agent

# Run all tests
.venv/bin/pytest datus-storage-postgresql/tests/ -v
```

## Adding a New Adapter

1. Create a new package directory at the repository root (e.g. `datus-storage-mysql/`)
2. Add its own `pyproject.toml` with dependencies and entry-points
3. Implement `BaseRdbBackend` and/or `BaseVectorBackend` under `datus_storage_<adapter_name>/`
4. Register the new member in the root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = [
    "datus-storage-base",
    "datus-storage-postgresql",
    "datus-storage-mysql",
]
```

5. Add a `README.md` inside the new package and link it from this file

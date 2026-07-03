# datus-storage-oceanbase-mysql

`datus-storage-oceanbase-mysql` provides Datus storage RDB and vector backends for OceanBase MySQL mode.

The RDB adapter stores structured Datus metadata. The vector adapter stores embeddings in OceanBase `VECTOR(N)` columns and uses OceanBase vector distance functions for nearest-neighbor search.

## Install

```bash
pip install datus-storage-oceanbase-mysql
```

The package registers itself through the `datus.storage.rdb` entry point as `oceanbase-mysql`.

## Configuration

```yaml
storage:
  isolation: logical
  rdb:
    type: oceanbase-mysql
    host: ${OB_HOST:-127.0.0.1}
    port: ${OB_PORT:-2881}
    user: ${OB_USER}
    password: ${OB_PASSWORD}
    database: datus_storage
    pool_min_size: 1
    pool_max_size: 5
  vector:
    type: oceanbase-mysql
    host: ${OB_HOST:-127.0.0.1}
    port: ${OB_PORT:-2881}
    user: ${OB_USER}
    password: ${OB_PASSWORD}
    database: datus_storage
    pool_max_size: 5
```

## Notes

- OceanBase MySQL mode does not support PostgreSQL schemas. `physical` isolation maps each Datus project namespace to a separate OceanBase database named `<namespace>__<store>`. `logical` isolation stores rows in the configured database and adds an internal `_datus_namespace` column to tables.
- The configured user needs permission to create databases when `physical` isolation is used.
- Business datasource execution should continue to use database adapters such as `datus-mysql` or a dedicated OceanBase datasource adapter.

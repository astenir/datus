# Datus OceanBase Oracle Adapter

OceanBase Oracle mode adapter for Datus.

The adapter connects through OceanBase Connector/J. Provide the path to an
`oceanbase-client` JDBC jar with `jar_path`.

```python
from datus_oceanbase_oracle import OceanBaseOracleConnector

connector = OceanBaseOracleConnector(
    {
        "host": "127.0.0.1",
        "port": 2883,
        "username": "app@oracle_tenant#obcluster",
        "password": "secret",
        "schema": "APP",
        "jar_path": "/path/to/oceanbase-client.jar",
    }
)
```

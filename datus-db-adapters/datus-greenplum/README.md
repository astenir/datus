# datus-greenplum

Greenplum database adapter for [Datus](https://github.com/Datus-ai/datus-agent).

## Installation

```bash
pip install datus-greenplum
```

## Usage

```python
from datus_greenplum import GreenplumConfig, GreenplumConnector

config = GreenplumConfig(
    host="localhost",
    port=5432,
    username="gpadmin",
    password="pivotal",
    database="mydb",
)

connector = GreenplumConnector(config)
result = connector.execute({"sql_query": "SELECT 1"}, result_format="list")
print(result.sql_return)
```

## Testing

```bash
# Unit tests (no database required)
cd datus-greenplum && python -m pytest tests/unit/ -v

# Integration tests (requires running Greenplum)
cd datus-greenplum
docker-compose up -d
python -m pytest tests/integration/ -v
```

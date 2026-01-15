# datus-hive

Hive database adapter for Datus.

## Installation

```bash
pip install datus-hive
```

This will automatically install the required dependencies:
- `datus-agent`
- `datus-sqlalchemy`
- `pyhive`
- `thrift`
- `thrift-sasl`
- `pure-sasl`
- `jaydebeapi`

## Usage

Configure your Hive connection in your Datus configuration:

```yaml
namespace:
  hive_db:
    type: hive
    host: 127.0.0.1
    port: 10001
    database: test
    username: hue
    password: your_password
    auth: CUSTOM
    configuration:
      hive.execution.engine: spark
      spark.app.name: datacenter_carrier
      spark.submit.deployMode: cluster
      spark.master: yarn
      spark.executor.memory: 1G
      spark.driver.memory: 1G
      spark.executor.cores: 2
      spark.driver.cores: 1
      spark.executor.instances: 1
      spark.yarn.queue: default
      spark.default.parallelism: 100
      spark.sql.shuffle.partitions: 100
      spark.memory.fraction: 0.8
      spark.memory.storageFraction: 0.3
      kyuubi.engine.share.level.subdomain: datacenter_carrier_connection
      spark.hadoop.fs.oss.buffer.size: 262144
      spark.hadoop.fs.oss.download.buffer.size: 262144
      spark.shuffle.compress: true
      spark.shuffle.spill.compress: true
    spark.io.compression.codec: lz4
```

Or use programmatically:

```python
from datus_hive import HiveConnector, HiveConfig

config = HiveConfig(
    host="127.0.0.1",
    port=10001,
    database="test",
    username="hue",
    password="your_password",
    auth="CUSTOM",
    configuration={
        "hive.execution.engine": "spark",
        "spark.app.name": "datacenter_carrier",
    },
)

connector = HiveConnector(config)
connector.test_connection()
```

## Testing

### Quick Start

```bash
# Unit tests
uv run pytest tests/unit -v

# Integration tests (requires Hive)
docker-compose up -d
uv run pytest tests/integration -m integration -v
docker-compose down
```


## License

Apache License 2.0

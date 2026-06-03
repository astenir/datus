# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.


def test_oracle_connection_smoke(oracle_connector):
    result = oracle_connector.execute({"sql_query": "SELECT 1 AS value FROM DUAL"}, result_format="list")

    assert result.success is True


def test_oracle_metadata_smoke(oracle_connector, oracle_config):
    schemas = oracle_connector.get_schemas(include_sys=False)

    assert oracle_config.schema_name in schemas

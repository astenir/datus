# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_db_core.testing import contract
from datus_spark import SparkConfig, SparkConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_deep_adapter_contract(connector: SparkConnector, config: SparkConfig):
    """Cover database-qualified SELECT, quoted identifiers, typed values, and LIMIT."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"contract_{suffix}"
    q = connector.quote_identifier
    database = config.database or "default"
    table_ref = f"{q(database)}.{q(table_name)}"

    case = contract.TableContractCase(
        adapter_name="spark",
        table_name=table_name,
        drop_sql=f"DROP TABLE IF EXISTS {table_ref}",
        create_sql=f"""
            CREATE TABLE {table_ref} (
                {q("id")} INT,
                {q("Mixed Case")} STRING,
                {q("nullable_text")} STRING,
                {q("event_date")} DATE,
                {q("amount")} DECIMAL(10, 2)
            ) USING PARQUET
        """,
        insert_sqls=[
            f"""
            INSERT INTO {table_ref} VALUES
                (1, 'Alpha', NULL, DATE '2024-02-03', CAST(123.45 AS DECIMAL(10, 2))),
                (2, 'Beta', 'present', DATE '2024-02-04', CAST(67.89 AS DECIMAL(10, 2)))
            """
        ],
        qualified_select_sql=f"""
            SELECT
                {q("id")} AS id_value,
                {q("Mixed Case")} AS mixed_value,
                {q("nullable_text")} AS nullable_value,
                {q("event_date")} AS event_date_value,
                {q("amount")} AS amount_value
            FROM {table_ref}
            ORDER BY {q("id")}
        """,
        limit_sql=f"SELECT {q('id')} AS id_value FROM {table_ref} ORDER BY {q('id')} LIMIT 1",
        schema_kwargs={"database_name": database},
        expected_columns=("id", "Mixed Case", "nullable_text", "event_date", "amount"),
    )

    contract.assert_table_contract(connector, case)

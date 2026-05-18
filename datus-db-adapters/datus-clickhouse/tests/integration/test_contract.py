# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector
from datus_db_core.testing import contract


@pytest.mark.integration
@pytest.mark.acceptance
def test_deep_adapter_contract(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Cover database-qualified SELECT, quoted identifiers, typed values, and LIMIT."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"contract_{suffix}"
    q = connector.quote_identifier
    database = config.database or "default"
    table_ref = f"{q(database)}.{q(table_name)}"

    case = contract.TableContractCase(
        adapter_name="clickhouse",
        table_name=table_name,
        drop_sql=f"DROP TABLE IF EXISTS {table_ref}",
        create_sql=f"""
            CREATE TABLE {table_ref} (
                {q("id")} Int64,
                {q("Mixed Case")} Nullable(String),
                {q("special-name")} Nullable(String),
                {q("nullable_text")} Nullable(String),
                {q("event_date")} Date,
                {q("event_ts")} DateTime,
                {q("amount")} Decimal(10, 2),
                {q("bool_flag")} Bool
            ) ENGINE = MergeTree()
            ORDER BY {q("id")}
        """,
        insert_sqls=[
            f"""
            INSERT INTO {table_ref}
                (
                    {q("id")},
                    {q("Mixed Case")},
                    {q("special-name")},
                    {q("nullable_text")},
                    {q("event_date")},
                    {q("event_ts")},
                    {q("amount")},
                    {q("bool_flag")}
                )
            VALUES
                (1, 'Alpha', 'S-1', NULL, toDate('2024-02-03'), toDateTime('2024-02-03 04:05:06'), 123.45, true),
                (2, 'Beta', 'S-2', 'present', toDate('2024-02-04'), toDateTime('2024-02-04 05:06:07'), 67.89, false)
            """
        ],
        qualified_select_sql=f"""
            SELECT
                {q("id")} AS id_value,
                {q("Mixed Case")} AS mixed_value,
                {q("special-name")} AS special_value,
                {q("nullable_text")} AS nullable_value,
                {q("event_date")} AS event_date_value,
                {q("event_ts")} AS event_ts_value,
                {q("amount")} AS amount_value,
                {q("bool_flag")} AS bool_value
            FROM {table_ref}
            ORDER BY {q("id")}
        """,
        limit_sql=f"SELECT {q('id')} AS id_value FROM {table_ref} ORDER BY {q('id')} LIMIT 1",
        schema_kwargs={"database_name": database},
        expected_columns=(
            "id",
            "Mixed Case",
            "special-name",
            "nullable_text",
            "event_date",
            "event_ts",
            "amount",
            "bool_flag",
        ),
        dialect_select_sqls=(f"SELECT toTypeName({q('amount')}) AS amount_type FROM {table_ref} LIMIT 1",),
    )

    contract.assert_table_contract(connector, case)

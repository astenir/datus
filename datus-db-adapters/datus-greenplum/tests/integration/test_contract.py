# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_db_core.testing import contract
from datus_greenplum import GreenplumConfig, GreenplumConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_deep_adapter_contract(connector: GreenplumConnector, config: GreenplumConfig):
    """Cover schema-qualified SELECT, quoted identifiers, typed values, and LIMIT."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"contract_{suffix}"
    q = connector.quote_identifier
    schema = config.schema_name or "public"
    table_ref = f"{q(schema)}.{q(table_name)}"

    case = contract.TableContractCase(
        adapter_name="greenplum",
        table_name=table_name,
        drop_sql=f"DROP TABLE IF EXISTS {table_ref}",
        create_sql=f"""
            CREATE TABLE {table_ref} (
                {q("id")} INTEGER,
                {q("Mixed Case")} VARCHAR(64),
                {q("nullable_text")} VARCHAR(64),
                {q("event_date")} DATE,
                {q("amount")} DECIMAL(10, 2)
            ) DISTRIBUTED BY ({q("id")})
        """,
        insert_sqls=[
            f"""
            INSERT INTO {table_ref}
                ({q("id")}, {q("Mixed Case")}, {q("nullable_text")}, {q("event_date")}, {q("amount")})
            VALUES
                (1, 'Alpha', NULL, '2024-02-03', 123.45),
                (2, 'Beta', 'present', '2024-02-04', 67.89)
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
        schema_kwargs={"schema_name": schema},
        expected_columns=("id", "Mixed Case", "nullable_text", "event_date", "amount"),
    )

    contract.assert_table_contract(connector, case)

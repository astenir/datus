# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest

from datus_db_core.testing import contract
from datus_trino import TrinoConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_deep_adapter_contract(tpch_connector: TrinoConnector):
    """Cover catalog/schema-qualified SELECT, quoted identifiers, typed values, and LIMIT."""
    case = contract.SelectContractCase(
        adapter_name="trino",
        select_sql="""
            SELECT
                id_value,
                "Mixed Case" AS mixed_value,
                nullable_value,
                event_date_value,
                amount_value
            FROM (
                VALUES
                    (1, 'Alpha', CAST(NULL AS VARCHAR), DATE '2024-02-03', DECIMAL '123.45'),
                    (2, 'Beta', 'present', DATE '2024-02-04', DECIMAL '67.89')
            ) AS t(id_value, "Mixed Case", nullable_value, event_date_value, amount_value)
            ORDER BY id_value
        """,
        limit_sql="""
            SELECT nationkey
            FROM "tpch"."tiny"."nation"
            ORDER BY nationkey
            LIMIT 1
        """,
        qualified_sql='SELECT COUNT(*) AS row_count FROM "tpch"."tiny"."orders"',
    )

    contract.assert_select_contract(tpch_connector, case)

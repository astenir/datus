import os

import pytest

from datus.tools.db_tools import SnowflakeConnector


@pytest.mark.parametrize(
    "warehouse,database_anme,schema_name",
    [("COMPUTE_WH_PARTICIPANT", "HACKER_NEWS", "HACKER_NEWS")],
)
def test_snowflake_connector(warehouse: str, database_anme: str, schema_name: str):
    connector = SnowflakeConnector(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=warehouse,
        database=database_anme,
        schema=schema_name,
    )
    connector.test_connection()

    res = connector.execute(
        {
            "sql_query": """select * from PATENTS_GOOGLE.PATENTS_GOOGLE.DISCLOSURES_13
            where "record_id" = 'REC00003' limit 10""",
        }
    )
    print(res.to_dict())


# test_snowflake_connector()

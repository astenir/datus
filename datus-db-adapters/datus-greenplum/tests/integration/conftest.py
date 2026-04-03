# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector

# ---------------------------------------------------------------------------
# TPC-H DDL & Data (PostgreSQL-compatible syntax for Greenplum)
# ---------------------------------------------------------------------------

TPCH_SCHEMA = "public"

TPCH_DDL = {
    "tpch_region": """
        CREATE TABLE "{schema}"."tpch_region" (
            "r_regionkey" INTEGER NOT NULL,
            "r_name" VARCHAR(25) NOT NULL,
            "r_comment" VARCHAR(152),
            PRIMARY KEY ("r_regionkey")
        )
    """,
    "tpch_nation": """
        CREATE TABLE "{schema}"."tpch_nation" (
            "n_nationkey" INTEGER NOT NULL,
            "n_name" VARCHAR(25) NOT NULL,
            "n_regionkey" INTEGER NOT NULL,
            "n_comment" VARCHAR(152),
            PRIMARY KEY ("n_nationkey")
        )
    """,
    "tpch_supplier": """
        CREATE TABLE "{schema}"."tpch_supplier" (
            "s_suppkey" INTEGER NOT NULL,
            "s_name" VARCHAR(25) NOT NULL,
            "s_address" VARCHAR(40) NOT NULL,
            "s_nationkey" INTEGER NOT NULL,
            "s_phone" VARCHAR(15) NOT NULL,
            "s_acctbal" DECIMAL(15,2) NOT NULL,
            "s_comment" VARCHAR(101),
            PRIMARY KEY ("s_suppkey")
        )
    """,
    "tpch_customer": """
        CREATE TABLE "{schema}"."tpch_customer" (
            "c_custkey" INTEGER NOT NULL,
            "c_name" VARCHAR(25) NOT NULL,
            "c_address" VARCHAR(40) NOT NULL,
            "c_nationkey" INTEGER NOT NULL,
            "c_phone" VARCHAR(15) NOT NULL,
            "c_acctbal" DECIMAL(15,2) NOT NULL,
            "c_mktsegment" VARCHAR(10) NOT NULL,
            "c_comment" VARCHAR(117),
            PRIMARY KEY ("c_custkey")
        )
    """,
    "tpch_orders": """
        CREATE TABLE "{schema}"."tpch_orders" (
            "o_orderkey" INTEGER NOT NULL,
            "o_custkey" INTEGER NOT NULL,
            "o_orderstatus" CHAR(1) NOT NULL,
            "o_totalprice" DECIMAL(15,2) NOT NULL,
            "o_orderdate" DATE NOT NULL,
            "o_orderpriority" VARCHAR(15) NOT NULL,
            "o_clerk" VARCHAR(15) NOT NULL,
            "o_shippriority" INTEGER NOT NULL,
            "o_comment" VARCHAR(79),
            PRIMARY KEY ("o_orderkey")
        )
    """,
}

TPCH_DATA = {
    "tpch_region": [
        (0, "AFRICA", "lar deposits. blithely final packages cajole."),
        (1, "AMERICA", "hs use ironic, even requests."),
        (2, "ASIA", "ges. thinly even pinto beans ca"),
        (3, "EUROPE", "ly final courts cajole furiously final excuse"),
        (4, "MIDDLE EAST", "uickly special accounts cajole carefully blithely close"),
    ],
    "tpch_nation": [
        (0, "ALGERIA", 0, " haggle. carefully final deposits detect slyly agai"),
        (1, "ARGENTINA", 1, "al foxes promise slyly according to the regular accounts."),
        (2, "BRAZIL", 1, "y alongside of the pending deposits."),
        (3, "CANADA", 1, "eas hang ironic, silent packages."),
        (4, "EGYPT", 4, "y above the carefully unusual theodolites."),
        (5, "ETHIOPIA", 0, "ven packages wake quickly."),
        (6, "FRANCE", 3, "refully final requests."),
        (7, "GERMANY", 3, "l platelets. regular accounts x-ray."),
        (8, "INDIA", 2, "ss excuses cajole slyly across the packages."),
        (9, "INDONESIA", 2, " slyly express asymptotes."),
        (10, "IRAN", 4, "efully alongside of the slyly final dependencies."),
        (11, "IRAQ", 4, "nic deposits boost atop the quickly final requests?"),
        (12, "JAPAN", 2, "ously. final, express gifts cajole a"),
        (13, "JORDAN", 4, "ic deposits are blithely about the carefully regular pa"),
        (14, "KENYA", 0, " pending excuses haggle furiously deposits."),
        (15, "MOROCCO", 0, "rns. blithely bold courts among the closely regular packages"),
        (16, "MOZAMBIQUE", 0, "s. ironic, unusual asymptotes wake blithely r"),
        (17, "PERU", 1, "platelets. blithely pending dependencies use fluffily"),
        (18, "CHINA", 2, "c dependencies. furiously express notornis sleep slyly"),
        (19, "ROMANIA", 3, "ular asymptotes are about the furious multipliers."),
        (20, "SAUDI ARABIA", 4, "ts. silent requests haggle. closely express packages"),
        (21, "VIETNAM", 2, "hely enticingly express accounts."),
        (22, "RUSSIA", 3, " requests against the platelets use never according to a"),
        (23, "UNITED KINGDOM", 3, "eans boost carefully special requests."),
        (24, "UNITED STATES", 1, "y final packages. slow foxes cajole quickly."),
    ],
    "tpch_supplier": [
        (
            1,
            "Supplier#000000001",
            "N kD4on9OM Ipw3,gf0JBoQDd7tgrzrddZ",
            17,
            "27-918-335-1736",
            5755.94,
            "each slyly above the careful",
        ),
        (2, "Supplier#000000002", "89eJ5ksX3ImxJQBvxObC,", 5, "15-679-861-2259", 4032.68, " slyly bold instructions."),
        (
            3,
            "Supplier#000000003",
            "q1,G3Pj6OjIuUYfUoH18BFTKP5aU9bEV3",
            1,
            "11-383-516-1199",
            4192.40,
            "blithely silent requests after the express dependencies",
        ),
        (
            4,
            "Supplier#000000004",
            "Bk7ah4CK8SYQTepEmvMkkgMwg",
            15,
            "25-843-787-7479",
            4641.08,
            "riously even requests above the exp",
        ),
        (5, "Supplier#000000005", "Gcdm2rJRzl5qlTVzc", 11, "21-151-690-3663", -531.44, ". slyly regular pinto beans t"),
    ],
    "tpch_customer": [
        (
            1,
            "Customer#000000001",
            "IVhzIApeRb",
            15,
            "25-989-741-2988",
            711.56,
            "BUILDING",
            "to the even, regular platelets.",
        ),
        (
            2,
            "Customer#000000002",
            "XSTf4,NCwDVaWNe6tEgvwfmRchLXak",
            13,
            "23-768-687-3665",
            121.65,
            "AUTOMOBILE",
            "l accounts. blithely ironic theodolites integrate boldly.",
        ),
        (
            3,
            "Customer#000000003",
            "MG9kdTD2WBHm",
            1,
            "11-719-748-3364",
            7498.12,
            "AUTOMOBILE",
            " deposits eat slyly ironic, even instructions.",
        ),
        (
            4,
            "Customer#000000004",
            "XxVSJsLAGtn",
            4,
            "14-128-190-5944",
            2866.83,
            "MACHINERY",
            " requests. final, regular ideas sleep final accou",
        ),
        (
            5,
            "Customer#000000005",
            "KvpyuHCplrB84WgAiGV6sYpZq7Tj",
            3,
            "13-750-942-6364",
            794.47,
            "HOUSEHOLD",
            "n accounts will have to unwind.",
        ),
    ],
    "tpch_orders": [
        (1, 1, "O", 173665.47, "1996-01-02", "5-LOW", "Clerk#000000951", 0, "nstructions sleep furiously among"),
        (
            2,
            2,
            "O",
            46929.18,
            "1996-12-01",
            "1-URGENT",
            "Clerk#000000880",
            0,
            " foxes. pending accounts at the pending",
        ),
        (3, 3, "F", 193846.25, "1993-10-14", "5-LOW", "Clerk#000000955", 0, "sly final accounts boost."),
        (4, 4, "O", 32151.78, "1995-10-11", "5-LOW", "Clerk#000000124", 0, "sits. slyly regular warthogs cajole."),
        (5, 5, "F", 144659.20, "1994-07-30", "5-LOW", "Clerk#000000925", 0, "quickly. bold deposits sleep slyly."),
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> GreenplumConfig:
    """Create Greenplum configuration for integration tests from environment or defaults."""
    return GreenplumConfig(
        host=os.getenv("GREENPLUM_HOST", "localhost"),
        port=int(os.getenv("GREENPLUM_PORT", "15432")),
        username=os.getenv("GREENPLUM_USER", "gpadmin"),
        password=os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        database=os.getenv("GREENPLUM_DATABASE", "test"),
        schema_name=os.getenv("GREENPLUM_SCHEMA", "public"),
    )


@pytest.fixture
def connector(config: GreenplumConfig) -> Generator[GreenplumConnector, None, None]:
    """Create and cleanup Greenplum connector for integration tests."""
    conn = None
    try:
        conn = GreenplumConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
        yield conn
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@pytest.fixture(scope="session")
def tpch_setup():
    """Set up TPC-H tables and data for integration tests (session-scoped).

    Creates tables, inserts sample data, yields for tests, then drops tables.
    Skips all tests if the database is not available.
    """
    cfg = GreenplumConfig(
        host=os.getenv("GREENPLUM_HOST", "localhost"),
        port=int(os.getenv("GREENPLUM_PORT", "15432")),
        username=os.getenv("GREENPLUM_USER", "gpadmin"),
        password=os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        database=os.getenv("GREENPLUM_DATABASE", "test"),
        schema_name=os.getenv("GREENPLUM_SCHEMA", "public"),
    )

    conn = None
    try:
        conn = GreenplumConnector(cfg)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    schema = cfg.schema_name or TPCH_SCHEMA

    def _escape_value(v) -> str:
        """Escape a value for SQL insertion."""
        if v is None:
            return "NULL"
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        return str(v)

    try:
        # Create tables
        for table_name, ddl in TPCH_DDL.items():
            conn.execute({"sql_query": f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE'})
            conn.execute({"sql_query": ddl.format(schema=schema)})

        # Insert data
        for table_name, rows in TPCH_DATA.items():
            for row in rows:
                values = ", ".join(_escape_value(v) for v in row)
                conn.execute({"sql_query": f'INSERT INTO "{schema}"."{table_name}" VALUES ({values})'})

        yield conn

    finally:
        # Cleanup: drop tables in reverse order
        for table_name in reversed(list(TPCH_DDL.keys())):
            try:
                conn.execute({"sql_query": f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE'})
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass

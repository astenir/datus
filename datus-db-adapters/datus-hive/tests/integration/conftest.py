# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import json
import os
from typing import Generator

import pytest
from datus_hive import HiveConfig, HiveConnector


def _load_configuration() -> dict:
    raw = os.getenv("HIVE_CONFIGURATION_JSON")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.skip(f"Invalid HIVE_CONFIGURATION_JSON: {exc}")
    if not isinstance(data, dict):
        pytest.skip("HIVE_CONFIGURATION_JSON must be a JSON object")
    return data


def _build_hive_config() -> HiveConfig:
    """Build HiveConfig from environment variables."""
    auth = os.getenv("HIVE_AUTH")
    return HiveConfig(
        host=os.getenv("HIVE_HOST", "localhost"),
        port=int(os.getenv("HIVE_PORT", "10000")),
        database=os.getenv("HIVE_DATABASE", "default"),
        username=os.getenv("HIVE_USERNAME", "hive"),
        password=os.getenv("HIVE_PASSWORD", ""),
        auth=auth if auth else None,
        configuration=_load_configuration(),
    )


@pytest.fixture
def config() -> HiveConfig:
    """Create Hive configuration for integration tests from environment or defaults."""
    return _build_hive_config()


@pytest.fixture
def connector(config: HiveConfig) -> Generator[HiveConnector, None, None]:
    """Create and cleanup Hive connector for integration tests."""
    conn = None
    try:
        conn = HiveConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as exc:
        pytest.skip(f"Database not available: {exc}")
    try:
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ==================== TPC-H Test Data ====================

TPCH_TABLES = [
    "tpch_region",
    "tpch_nation",
    "tpch_customer",
    "tpch_orders",
    "tpch_supplier",
]

TPCH_DDL = [
    """
    CREATE TABLE IF NOT EXISTS tpch_region (
        regionkey INT,
        name STRING,
        comment STRING
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tpch_nation (
        nationkey INT,
        name STRING,
        regionkey INT,
        comment STRING
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tpch_customer (
        custkey INT,
        name STRING,
        nationkey INT,
        acctbal DOUBLE,
        mktsegment STRING
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tpch_orders (
        orderkey INT,
        custkey INT,
        orderstatus STRING,
        totalprice DOUBLE,
        orderdate STRING
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tpch_supplier (
        suppkey INT,
        name STRING,
        nationkey INT,
        acctbal DOUBLE
    )
    """,
]

TPCH_DATA = [
    # region: 5 rows (standard TPC-H)
    """
    INSERT INTO tpch_region VALUES
    (0, 'AFRICA', 'special Tiresias about the furiously even'),
    (1, 'AMERICA', 'hs use ironic, even requests'),
    (2, 'ASIA', 'ges. thinly even pinto beans ca'),
    (3, 'EUROPE', 'ly final courts cajole furiously final excuse'),
    (4, 'MIDDLE EAST', 'uickly special accounts cajole carefully')
    """,
    # nation: 25 rows (standard TPC-H)
    """
    INSERT INTO tpch_nation VALUES
    (0, 'ALGERIA', 0, 'haggle. carefully final deposits'),
    (1, 'ARGENTINA', 1, 'al foxes promise slyly'),
    (2, 'BRAZIL', 1, 'y alongside of the pending deposits'),
    (3, 'CANADA', 1, 'eas hang ironic, silent packages'),
    (4, 'EGYPT', 4, 'y above the carefully unusual theodolites'),
    (5, 'ETHIOPIA', 0, 'ven packages was slyly'),
    (6, 'FRANCE', 3, 'refully final requests'),
    (7, 'GERMANY', 3, 'l platelets. regular accounts'),
    (8, 'INDIA', 2, 'ss excuses cajole slyly'),
    (9, 'INDONESIA', 2, 'slyly express asymptotes'),
    (10, 'IRAN', 4, 'efully alongside of the slyly final'),
    (11, 'IRAQ', 4, 'nic deposits boost atop the quickly final'),
    (12, 'JAPAN', 2, 'ously. final, express gifts cajole'),
    (13, 'JORDAN', 4, 'ic deposits are blithely about the carefully'),
    (14, 'KENYA', 0, 'pending excuses haggle furiously deposits'),
    (15, 'MOROCCO', 0, 'rns. blithely bold courts among the closely'),
    (16, 'MOZAMBIQUE', 0, 's. ironic, unusual asymptotes wake'),
    (17, 'PERU', 1, 'platelets. blithely pending dependencies'),
    (18, 'CHINA', 2, 'c dependencies. furiously express notornis'),
    (19, 'ROMANIA', 3, 'ular asymptotes are about the furious'),
    (20, 'SAUDI ARABIA', 4, 'ts. silent requests haggle'),
    (21, 'VIETNAM', 2, 'hely enticingly express accounts'),
    (22, 'RUSSIA', 3, 'requests against the platelets use'),
    (23, 'UNITED KINGDOM', 3, 'eans boost carefully special requests'),
    (24, 'UNITED STATES', 1, 'y final packages. slow foxes cajole')
    """,
    # customer: 10 rows (simplified)
    """
    INSERT INTO tpch_customer VALUES
    (1, 'Customer#001', 0, 711.56, 'BUILDING'),
    (2, 'Customer#002', 1, 121.65, 'AUTOMOBILE'),
    (3, 'Customer#003', 2, 7498.12, 'AUTOMOBILE'),
    (4, 'Customer#004', 3, 2866.83, 'MACHINERY'),
    (5, 'Customer#005', 4, 794.47, 'HOUSEHOLD'),
    (6, 'Customer#006', 5, 7638.57, 'AUTOMOBILE'),
    (7, 'Customer#007', 18, 9561.95, 'AUTOMOBILE'),
    (8, 'Customer#008', 8, 6819.74, 'BUILDING'),
    (9, 'Customer#009', 12, 8324.07, 'FURNITURE'),
    (10, 'Customer#010', 24, 2753.54, 'HOUSEHOLD')
    """,
    # orders: 15 rows (simplified)
    """
    INSERT INTO tpch_orders VALUES
    (1, 1, 'O', 173665.47, '1996-01-02'),
    (2, 2, 'O', 46929.18, '1996-12-01'),
    (3, 3, 'F', 193846.25, '1993-10-14'),
    (4, 4, 'O', 32151.78, '1995-10-11'),
    (5, 5, 'F', 144659.20, '1994-07-30'),
    (6, 1, 'F', 58749.59, '1992-02-21'),
    (7, 2, 'O', 252004.18, '1996-01-10'),
    (8, 3, 'O', 13309.60, '1995-10-11'),
    (9, 6, 'F', 51135.56, '1993-10-14'),
    (10, 7, 'F', 149149.20, '1993-12-18'),
    (11, 8, 'O', 79258.24, '1996-06-20'),
    (12, 9, 'F', 89911.07, '1993-01-29'),
    (13, 10, 'O', 159364.60, '1995-10-21'),
    (14, 1, 'O', 44694.46, '1995-10-22'),
    (15, 4, 'F', 32632.18, '1993-07-16')
    """,
    # supplier: 5 rows (simplified)
    """
    INSERT INTO tpch_supplier VALUES
    (1, 'Supplier#001', 0, 5755.94),
    (2, 'Supplier#002', 1, 4032.68),
    (3, 'Supplier#003', 8, 4192.40),
    (4, 'Supplier#004', 18, 1276.49),
    (5, 'Supplier#005', 24, 3956.15)
    """,
]


@pytest.fixture(scope="session")
def tpch_setup() -> Generator[HiveConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    hive_config = _build_hive_config()

    conn = None
    try:
        conn = HiveConnector(hive_config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")

        # Drop existing tables first to ensure clean state
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS {table}")

        # Create tables
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)

        # Insert data
        for data in TPCH_DATA:
            conn.execute_insert(data)

    except Exception as exc:
        pytest.skip(f"TPC-H setup failed: {exc}")
    else:
        yield conn
    finally:
        if conn is not None:
            try:
                for table in TPCH_TABLES:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

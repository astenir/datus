# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import logging
import os
from typing import Generator

import pytest
from datus_starrocks import StarRocksConfig, StarRocksConnector

logger = logging.getLogger(__name__)


@pytest.fixture
def config() -> StarRocksConfig:
    """Create StarRocks configuration from environment or defaults for integration tests."""
    return StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database=os.getenv("STARROCKS_DATABASE", "test"),
    )


@pytest.fixture
def connector(config: StarRocksConfig) -> Generator[StarRocksConnector, None, None]:
    """Create and cleanup StarRocks connector for integration tests."""
    conn = None
    try:
        conn = StarRocksConnector(config)
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
                logger.warning("Failed to close connector during teardown", exc_info=True)


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
    CREATE TABLE IF NOT EXISTS `tpch_region` (
        `regionkey` INT NOT NULL,
        `name` VARCHAR(25) NOT NULL,
        `comment` VARCHAR(152)
    ) ENGINE=OLAP
    PRIMARY KEY (`regionkey`)
    DISTRIBUTED BY HASH(`regionkey`) BUCKETS 1
    PROPERTIES ("replication_num" = "1")
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_nation` (
        `nationkey` INT NOT NULL,
        `name` VARCHAR(25) NOT NULL,
        `regionkey` INT NOT NULL,
        `comment` VARCHAR(152)
    ) ENGINE=OLAP
    PRIMARY KEY (`nationkey`)
    DISTRIBUTED BY HASH(`nationkey`) BUCKETS 1
    PROPERTIES ("replication_num" = "1")
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_customer` (
        `custkey` INT NOT NULL,
        `name` VARCHAR(25) NOT NULL,
        `nationkey` INT NOT NULL,
        `acctbal` DECIMAL(15,2) NOT NULL,
        `mktsegment` VARCHAR(10) NOT NULL
    ) ENGINE=OLAP
    PRIMARY KEY (`custkey`)
    DISTRIBUTED BY HASH(`custkey`) BUCKETS 1
    PROPERTIES ("replication_num" = "1")
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_orders` (
        `orderkey` INT NOT NULL,
        `custkey` INT NOT NULL,
        `orderstatus` VARCHAR(1) NOT NULL,
        `totalprice` DECIMAL(15,2) NOT NULL,
        `orderdate` DATE NOT NULL
    ) ENGINE=OLAP
    PRIMARY KEY (`orderkey`)
    DISTRIBUTED BY HASH(`orderkey`) BUCKETS 1
    PROPERTIES ("replication_num" = "1")
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_supplier` (
        `suppkey` INT NOT NULL,
        `name` VARCHAR(25) NOT NULL,
        `nationkey` INT NOT NULL,
        `acctbal` DECIMAL(15,2) NOT NULL
    ) ENGINE=OLAP
    PRIMARY KEY (`suppkey`)
    DISTRIBUTED BY HASH(`suppkey`) BUCKETS 1
    PROPERTIES ("replication_num" = "1")
    """,
]

TPCH_DATA = [
    """
    INSERT INTO `tpch_region` VALUES
    (0, 'AFRICA', 'special Tiresias about the furiously even'),
    (1, 'AMERICA', 'hs use ironic, even requests'),
    (2, 'ASIA', 'ges. thinly even pinto beans ca'),
    (3, 'EUROPE', 'ly final courts cajole furiously final excuse'),
    (4, 'MIDDLE EAST', 'uickly special accounts cajole carefully')
    """,
    """
    INSERT INTO `tpch_nation` VALUES
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
    """
    INSERT INTO `tpch_customer` VALUES
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
    """
    INSERT INTO `tpch_orders` VALUES
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
    """
    INSERT INTO `tpch_supplier` VALUES
    (1, 'Supplier#001', 0, 5755.94),
    (2, 'Supplier#002', 1, 4032.68),
    (3, 'Supplier#003', 8, 4192.40),
    (4, 'Supplier#004', 18, 1276.49),
    (5, 'Supplier#005', 24, 3956.15)
    """,
]

ROW_COUNTS = [5, 25, 10, 15, 5]


@pytest.fixture(scope="session")
def tpch_setup() -> Generator[StarRocksConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    tpch_config = StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database=os.getenv("STARROCKS_DATABASE", "test"),
    )

    conn = None
    # Only skip on connection failures; DDL/DML errors should propagate and fail
    # the suite so they are not silently hidden.
    try:
        conn = StarRocksConnector(tpch_config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    try:
        # Drop tables first for deterministic setup.
        # Errors here are real failures and must not be swallowed.
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")

        # Create tables
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)

        # Insert data
        for data in TPCH_DATA:
            conn.execute_insert(data)

        yield conn
    finally:
        if conn is not None:
            try:
                for table in TPCH_TABLES:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")
            except Exception:
                logger.warning("Failed to drop TPC-H tables during teardown", exc_info=True)
            try:
                conn.close()
            except Exception:
                logger.warning("Failed to close connection during teardown", exc_info=True)

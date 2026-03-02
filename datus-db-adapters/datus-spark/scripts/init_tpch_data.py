#!/usr/bin/env python3
# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Initialize TPC-H sample data in Spark Thrift Server.

Usage:
    # Start Spark first:
    cd datus-spark && docker compose up -d

    # Then run this script:
    uv run python scripts/init_tpch_data.py

    # With custom connection:
    uv run python scripts/init_tpch_data.py --host localhost --port 10000

    # Drop existing tables first (clean re-init):
    uv run python scripts/init_tpch_data.py --drop
"""

import argparse
import logging
import sys

# Suppress adapter registry warnings in workspace dev environment
logging.getLogger("datus.tools.db_tools.registry").setLevel(logging.ERROR)

from datus_spark import SparkConfig, SparkConnector  # noqa: E402

TPCH_DDL = [
    """
    CREATE TABLE IF NOT EXISTS `default`.`tpch_region` (
        regionkey INT, name STRING, comment STRING
    ) USING PARQUET
    """,
    """
    CREATE TABLE IF NOT EXISTS `default`.`tpch_nation` (
        nationkey INT, name STRING, regionkey INT, comment STRING
    ) USING PARQUET
    """,
    """
    CREATE TABLE IF NOT EXISTS `default`.`tpch_customer` (
        custkey INT, name STRING, nationkey INT, acctbal DOUBLE, mktsegment STRING
    ) USING PARQUET
    """,
    """
    CREATE TABLE IF NOT EXISTS `default`.`tpch_orders` (
        orderkey INT, custkey INT, orderstatus STRING, totalprice DOUBLE, orderdate STRING
    ) USING PARQUET
    """,
    """
    CREATE TABLE IF NOT EXISTS `default`.`tpch_supplier` (
        suppkey INT, name STRING, nationkey INT, acctbal DOUBLE
    ) USING PARQUET
    """,
]

TPCH_DATA = [
    # region: 5 rows (standard TPC-H)
    """
    INSERT INTO `default`.`tpch_region` VALUES
    (0, 'AFRICA', 'special Tiresias about the furiously even'),
    (1, 'AMERICA', 'hs use ironic, even requests'),
    (2, 'ASIA', 'ges. thinly even pinto beans ca'),
    (3, 'EUROPE', 'ly final courts cajole furiously final excuse'),
    (4, 'MIDDLE EAST', 'uickly special accounts cajole carefully')
    """,
    # nation: 25 rows (standard TPC-H)
    """
    INSERT INTO `default`.`tpch_nation` VALUES
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
    INSERT INTO `default`.`tpch_customer` VALUES
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
    INSERT INTO `default`.`tpch_orders` VALUES
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
    INSERT INTO `default`.`tpch_supplier` VALUES
    (1, 'Supplier#001', 0, 5755.94),
    (2, 'Supplier#002', 1, 4032.68),
    (3, 'Supplier#003', 8, 4192.40),
    (4, 'Supplier#004', 18, 1276.49),
    (5, 'Supplier#005', 24, 3956.15)
    """,
]

TPCH_TABLES = ["tpch_region", "tpch_nation", "tpch_customer", "tpch_orders", "tpch_supplier"]


def main():
    parser = argparse.ArgumentParser(description="Initialize TPC-H sample data in Spark")
    parser.add_argument("--host", default="localhost", help="Spark Thrift Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=10000, help="Spark Thrift Server port (default: 10000)")
    parser.add_argument("--username", default="spark", help="Username (default: spark)")
    parser.add_argument("--database", default="default", help="Database (default: default)")
    parser.add_argument("--drop", action="store_true", help="Drop existing TPC-H tables before creating")
    args = parser.parse_args()

    config = SparkConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password="",
        database=args.database,
        auth_mechanism="NONE",
    )

    print(f"Connecting to Spark at {args.host}:{args.port}...")
    conn = SparkConnector(config)

    if not conn.test_connection():
        print("Failed to connect to Spark. Is the Thrift Server running?")
        print("  Start it with: cd datus-spark && docker compose up -d")
        sys.exit(1)

    print("Connected successfully!")

    if args.drop:
        print("\nDropping existing TPC-H tables...")
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS `default`.`{table}`")
            print(f"  Dropped {table}")

    print("\nCreating TPC-H tables...")
    for i, ddl in enumerate(TPCH_DDL):
        conn.execute_ddl(ddl)
        print(f"  Created {TPCH_TABLES[i]}")

    print("\nInserting TPC-H data...")
    row_counts = [5, 25, 10, 15, 5]
    for i, data in enumerate(TPCH_DATA):
        conn.execute_ddl(data)
        print(f"  Inserted {row_counts[i]} rows into {TPCH_TABLES[i]}")

    # Verify
    print("\nVerifying data...")
    for i, table in enumerate(TPCH_TABLES):
        result = conn.execute(
            {"sql_query": f"SELECT COUNT(*) AS cnt FROM `default`.`{table}`"},
            result_format="list",
        )
        count = result.sql_return[0]["cnt"]
        expected = row_counts[i]
        status = "OK" if count >= expected else "MISMATCH"
        print(f"  {table}: {count} rows [{status}]")

    conn.close()
    print("\nDone! TPC-H data is ready for use in Datus.")
    print("\nExample queries:")
    print("  SELECT * FROM `default`.`tpch_region`")
    print(
        "  SELECT n.name, r.name FROM `default`.`tpch_nation` n"
        " JOIN `default`.`tpch_region` r ON n.regionkey = r.regionkey"
    )


if __name__ == "__main__":
    main()

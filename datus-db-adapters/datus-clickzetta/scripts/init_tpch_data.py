#!/usr/bin/env python3
# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Initialize TPC-H sample data in ClickZetta Lakehouse.

Usage:
    # Set environment variables first:
    export CLICKZETTA_SERVICE="your-service.clickzetta.com"
    export CLICKZETTA_USERNAME="your-username"
    export CLICKZETTA_PASSWORD="your-password"
    export CLICKZETTA_INSTANCE="your-instance"
    export CLICKZETTA_WORKSPACE="your-workspace"

    # Then run this script:
    uv run python scripts/init_tpch_data.py

    # Drop existing tables first (clean re-init):
    uv run python scripts/init_tpch_data.py --drop
"""

import argparse
import getpass
import logging
import os
import sys

# Suppress adapter registry warnings in workspace dev environment
logging.getLogger("datus.tools.db_tools.registry").setLevel(logging.ERROR)

from datus_clickzetta.connector import ClickZettaConnector  # noqa: E402

TPCH_DDL = [
    """
    CREATE TABLE IF NOT EXISTS `tpch_region` (
        `regionkey` INT,
        `name` VARCHAR(25),
        `comment` VARCHAR(152)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_nation` (
        `nationkey` INT,
        `name` VARCHAR(25),
        `regionkey` INT,
        `comment` VARCHAR(152)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_customer` (
        `custkey` INT,
        `name` VARCHAR(25),
        `nationkey` INT,
        `acctbal` DECIMAL(15,2),
        `mktsegment` VARCHAR(10)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_orders` (
        `orderkey` INT,
        `custkey` INT,
        `orderstatus` VARCHAR(1),
        `totalprice` DECIMAL(15,2),
        `orderdate` VARCHAR(10)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_supplier` (
        `suppkey` INT,
        `name` VARCHAR(25),
        `nationkey` INT,
        `acctbal` DECIMAL(15,2)
    )
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

TPCH_TABLES = ["tpch_region", "tpch_nation", "tpch_customer", "tpch_orders", "tpch_supplier"]
ROW_COUNTS = [5, 25, 10, 15, 5]


def main():
    parser = argparse.ArgumentParser(description="Initialize TPC-H sample data in ClickZetta")
    parser.add_argument("--service", default=os.getenv("CLICKZETTA_SERVICE", ""))
    parser.add_argument("--username", default=os.getenv("CLICKZETTA_USERNAME", ""))
    parser.add_argument("--instance", default=os.getenv("CLICKZETTA_INSTANCE", ""))
    parser.add_argument("--workspace", default=os.getenv("CLICKZETTA_WORKSPACE", ""))
    parser.add_argument("--schema", default=os.getenv("CLICKZETTA_SCHEMA", "PUBLIC"))
    parser.add_argument("--vcluster", default=os.getenv("CLICKZETTA_VCLUSTER", "DEFAULT_AP"))
    parser.add_argument("--drop", action="store_true", help="Drop existing TPC-H tables before creating")
    args = parser.parse_args()

    password = os.getenv("CLICKZETTA_PASSWORD", "")
    if not password:
        password = getpass.getpass("ClickZetta password: ")

    # Validate required fields
    required = {
        "service": args.service,
        "username": args.username,
        "password": password,
        "instance": args.instance,
        "workspace": args.workspace,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"Error: Missing required fields: {', '.join(missing)}")
        print("Set via environment variables or command-line arguments.")
        print("  export CLICKZETTA_SERVICE=your-service.clickzetta.com")
        print("  export CLICKZETTA_USERNAME=your-username")
        print("  export CLICKZETTA_PASSWORD=your-password")
        print("  export CLICKZETTA_INSTANCE=your-instance")
        print("  export CLICKZETTA_WORKSPACE=your-workspace")
        sys.exit(1)

    print(f"Connecting to ClickZetta at {args.service}...")
    conn = ClickZettaConnector(
        service=args.service,
        username=args.username,
        password=password,
        instance=args.instance,
        workspace=args.workspace,
        schema=args.schema,
        vcluster=args.vcluster,
    )

    try:
        conn.test_connection()
        print("Connected successfully!")

        if args.drop:
            print("\nDropping existing TPC-H tables...")
            for table in TPCH_TABLES:
                drop_result = conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")
                if not drop_result.success:
                    print(f"  Failed dropping {table}: {drop_result.error}")
                    sys.exit(2)
                print(f"  Dropped {table}")

        print("\nCreating TPC-H tables...")
        for i, ddl in enumerate(TPCH_DDL):
            ddl_result = conn.execute_ddl(ddl)
            if not ddl_result.success:
                print(f"  Failed creating {TPCH_TABLES[i]}: {ddl_result.error}")
                sys.exit(2)
            print(f"  Created {TPCH_TABLES[i]}")

        print("\nInserting TPC-H data...")
        for i, data in enumerate(TPCH_DATA):
            insert_result = conn.execute_insert(data)
            if not insert_result.success:
                print(f"  Failed inserting into {TPCH_TABLES[i]}: {insert_result.error}")
                sys.exit(2)
            print(f"  Inserted {ROW_COUNTS[i]} rows into {TPCH_TABLES[i]}")

        # Verify
        print("\nVerifying data...")
        has_mismatch = False
        for i, table in enumerate(TPCH_TABLES):
            result = conn.execute_query(
                f"SELECT COUNT(*) AS cnt FROM `{table}`",
                result_format="list",
            )
            if not result.success:
                print(f"  {table}: query failed [{result.error}]")
                has_mismatch = True
                continue
            if result.sql_return and isinstance(result.sql_return[0], dict) and "cnt" in result.sql_return[0]:
                count = int(result.sql_return[0]["cnt"])
            else:
                print(f"  {table}: unexpected query result")
                has_mismatch = True
                continue
            expected = ROW_COUNTS[i]
            status = "OK" if count == expected else "MISMATCH"
            if count != expected:
                has_mismatch = True
            print(f"  {table}: {count} rows [{status}]")

        if has_mismatch:
            print("\nVerification failed. Re-run with --drop for a clean re-init.")
            sys.exit(2)
    finally:
        conn.close()

    print("\nDone! TPC-H data is ready for use in Datus.")
    print("\nExample queries:")
    print("  SELECT * FROM `tpch_region`")
    print("  SELECT n.name, r.name FROM `tpch_nation` n" " JOIN `tpch_region` r ON n.regionkey = r.regionkey")


if __name__ == "__main__":
    main()

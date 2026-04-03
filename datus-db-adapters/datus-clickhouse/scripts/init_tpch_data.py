#!/usr/bin/env python3
# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Initialize TPC-H sample data in ClickHouse.

Usage:
    # Start ClickHouse first:
    cd datus-clickhouse && docker compose up -d

    # Then run this script:
    uv run python scripts/init_tpch_data.py

    # With custom connection:
    uv run python scripts/init_tpch_data.py --host localhost --port 8123 --username default_user --password default_test

    # Drop existing tables first (clean re-init):
    uv run python scripts/init_tpch_data.py --drop
"""

import argparse
import logging
import sys

# Suppress adapter registry warnings in workspace dev environment
logging.getLogger("datus.tools.db_tools.registry").setLevel(logging.ERROR)

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector  # noqa: E402
from datus_clickhouse.tpch_data import ROW_COUNTS, TPCH_DATA, TPCH_DDL, TPCH_TABLES  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Initialize TPC-H sample data in ClickHouse")
    parser.add_argument("--host", default="localhost", help="ClickHouse host (default: localhost)")
    parser.add_argument("--port", type=int, default=8123, help="ClickHouse HTTP port (default: 8123)")
    parser.add_argument("--username", default="default_user", help="Username (default: default_user)")
    parser.add_argument("--password", default="default_test", help="Password (default: default_test)")
    parser.add_argument("--database", default="default_test", help="Database (default: default_test)")
    parser.add_argument("--drop", action="store_true", help="Drop existing TPC-H tables before creating")
    args = parser.parse_args()

    # First ensure database exists
    print(f"Connecting to ClickHouse at {args.host}:{args.port}...")
    init_config = ClickHouseConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        database=None,
    )
    init_conn = ClickHouseConnector(init_config)

    if not init_conn.test_connection():
        print("Failed to connect to ClickHouse. Is the server running?")
        print("  Start it with: cd datus-clickhouse && docker compose up -d")
        sys.exit(1)

    print("Connected successfully!")
    print(f"\nEnsuring database `{args.database}` exists...")
    init_conn.execute_ddl(f"CREATE DATABASE IF NOT EXISTS `{args.database}`")
    init_conn.close()

    # Connect to target database
    config = ClickHouseConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    conn = ClickHouseConnector(config)
    try:
        if args.drop:
            print("\nDropping existing TPC-H tables...")
            for table in TPCH_TABLES:
                conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")
                print(f"  Dropped {table}")

        print("\nCreating TPC-H tables...")
        for i, ddl in enumerate(TPCH_DDL):
            conn.execute_ddl(ddl)
            print(f"  Created {TPCH_TABLES[i]}")

        print("\nInserting TPC-H data...")
        for i, data in enumerate(TPCH_DATA):
            conn.execute_insert(data)
            print(f"  Inserted {ROW_COUNTS[i]} rows into {TPCH_TABLES[i]}")

        # Verify
        print("\nVerifying data...")
        has_mismatch = False
        for i, table in enumerate(TPCH_TABLES):
            result = conn.execute(
                {"sql_query": f"SELECT COUNT(*) AS cnt FROM `{table}`"},
                result_format="list",
            )
            count = result.sql_return[0]["cnt"]
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
    print("  SELECT n.name, r.name FROM `tpch_nation` n JOIN `tpch_region` r ON n.regionkey = r.regionkey")


if __name__ == "__main__":
    main()

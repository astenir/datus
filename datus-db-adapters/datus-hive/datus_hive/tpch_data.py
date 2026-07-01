# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Hive-dialect TPC-H test data definitions."""

from datus_db_core.testing.tpch import ROW_COUNTS, TPCH_TABLES, build_tpch_inserts

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

TPCH_DATA = build_tpch_inserts()

__all__ = ["TPCH_DDL", "TPCH_DATA", "TPCH_TABLES", "ROW_COUNTS"]

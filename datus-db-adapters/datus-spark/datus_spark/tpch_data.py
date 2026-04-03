# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Spark-dialect TPC-H test data definitions."""

from datus_db_core.testing.tpch import ROW_COUNTS, TPCH_TABLES, build_tpch_inserts

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

TPCH_DATA = build_tpch_inserts(lambda t: f"`default`.`{t}`")

__all__ = ["TPCH_DDL", "TPCH_DATA", "TPCH_TABLES", "ROW_COUNTS"]

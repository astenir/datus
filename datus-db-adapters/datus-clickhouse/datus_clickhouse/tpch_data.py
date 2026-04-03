# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""ClickHouse-dialect TPC-H test data definitions."""

from datus_db_core.testing.tpch import ROW_COUNTS, TPCH_TABLES, build_tpch_inserts

TPCH_DDL = [
    """
    CREATE TABLE IF NOT EXISTS `tpch_region` (
        `regionkey` Int32,
        `name` String,
        `comment` String
    ) ENGINE = MergeTree() ORDER BY regionkey
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_nation` (
        `nationkey` Int32,
        `name` String,
        `regionkey` Int32,
        `comment` String
    ) ENGINE = MergeTree() ORDER BY nationkey
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_customer` (
        `custkey` Int32,
        `name` String,
        `nationkey` Int32,
        `acctbal` Float64,
        `mktsegment` String
    ) ENGINE = MergeTree() ORDER BY custkey
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_orders` (
        `orderkey` Int32,
        `custkey` Int32,
        `orderstatus` String,
        `totalprice` Float64,
        `orderdate` String
    ) ENGINE = MergeTree() ORDER BY orderkey
    """,
    """
    CREATE TABLE IF NOT EXISTS `tpch_supplier` (
        `suppkey` Int32,
        `name` String,
        `nationkey` Int32,
        `acctbal` Float64
    ) ENGINE = MergeTree() ORDER BY suppkey
    """,
]

TPCH_DATA = build_tpch_inserts(lambda t: f"`{t}`")

__all__ = ["TPCH_DDL", "TPCH_DATA", "TPCH_TABLES", "ROW_COUNTS"]

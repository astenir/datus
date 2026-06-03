# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from datus_oracle import OracleConfig
from datus_oracle.handlers import build_oracle_uri, resolve_oracle_context


def test_build_oracle_uri_with_service_name():
    config = OracleConfig(
        host="db.example.com",
        port=1522,
        username="app",
        password="p@ss word",
        service_name="SALES",
    )

    uri = build_oracle_uri(config)

    assert uri.startswith("oracle+oracledb://app:p%40ss%20word@db.example.com:1522/")
    assert "service_name=SALES" in uri


def test_build_oracle_uri_with_sid():
    config = OracleConfig(username="app", sid="XE", service_name=None)

    uri = build_oracle_uri(config)

    assert "sid=XE" in uri
    assert "service_name" not in uri


def test_resolve_oracle_context_prefers_query_schema():
    config = OracleConfig(username="app", service_name="FREEPDB1", schema="APP")
    uri = "oracle+oracledb://app:secret@localhost:1521/?service_name=FREEPDB1&schema=reporting"

    dialect, catalog, database, schema = resolve_oracle_context(config, uri)

    assert dialect == "oracle"
    assert catalog == ""
    assert database == "FREEPDB1"
    assert schema == "REPORTING"


def test_resolve_oracle_context_uses_sid_as_database_when_no_service_name():
    config = OracleConfig(username="app", sid="XE", service_name=None)
    uri = "oracle+oracledb://app:secret@localhost:1521/?sid=XE"

    assert resolve_oracle_context(config, uri) == ("oracle", "", "XE", "APP")

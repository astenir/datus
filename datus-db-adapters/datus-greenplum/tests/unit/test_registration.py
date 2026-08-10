# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from unittest.mock import patch

import datus_greenplum


def test_register_declares_postgres_parser_dialect() -> None:
    with patch("datus_db_core.connector_registry.register") as register_connector:
        datus_greenplum.register()

    assert register_connector.call_args.kwargs["parser_dialect"] == "postgres"

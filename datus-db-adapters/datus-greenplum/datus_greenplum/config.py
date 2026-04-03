# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from datus_postgresql import PostgreSQLConfig


class GreenplumConfig(PostgreSQLConfig):
    """Greenplum-specific configuration.

    Inherits all fields from PostgreSQLConfig since Greenplum uses
    the same connection parameters and PostgreSQL wire protocol.
    """

    pass

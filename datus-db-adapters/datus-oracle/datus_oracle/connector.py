# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import List, Set, Union, override

from datus_db_core import MigrationTargetMixin
from datus_sqlalchemy import SQLAlchemyConnector

from .config import OracleConfig
from .handlers import build_oracle_uri


class OracleConnector(SQLAlchemyConnector, MigrationTargetMixin):
    """Oracle database connector."""

    def __init__(self, config: Union[OracleConfig, dict]):
        if isinstance(config, dict):
            config = OracleConfig(**config)
        elif not isinstance(config, OracleConfig):
            raise TypeError(f"config must be OracleConfig or dict, got {type(config)}")

        self.config = config
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        database = config.database
        schema = config.schema_name or config.username.upper()

        super().__init__(
            build_oracle_uri(config),
            dialect="oracle",
            timeout_seconds=config.timeout_seconds,
        )
        self.config = config
        self._default_database = database
        self._default_schema = schema

    @override
    def _sys_databases(self) -> Set[str]:
        return set()

    @override
    def _sys_schemas(self) -> Set[str]:
        return {
            "SYS",
            "SYSTEM",
            "OUTLN",
            "DBSNMP",
            "APPQOSSYS",
            "AUDSYS",
            "CTXSYS",
            "GSMADMIN_INTERNAL",
            "MDSYS",
            "OJVMSYS",
            "ORDDATA",
            "ORDSYS",
            "XDB",
            "WMSYS",
        }

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        return [self.database_name] if self.database_name else []

    @override
    def quote_identifier(self, name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @override
    def full_name(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        schema_name = schema_name or self.schema_name
        if schema_name:
            return f"{self.quote_identifier(schema_name)}.{self.quote_identifier(table_name)}"
        return self.quote_identifier(table_name)

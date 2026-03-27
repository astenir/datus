# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""URI builder and context resolver for PostgreSQL."""

import re
from typing import Dict, Optional, Tuple, Union
from urllib.parse import unquote

from sqlalchemy.engine.url import URL, make_url


def _clean_str(value: Optional[Union[str, int]]) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if item:
                return str(item).strip()
        return ""
    return str(value).strip()


def _value_or_none(value: Optional[Union[str, int]]) -> Optional[str]:
    cleaned = _clean_str(value)
    return cleaned or None


def _port_or_none(port_value: Optional[Union[str, int]]) -> Optional[int]:
    cleaned = _clean_str(port_value)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _extract_schema_from_pg_options(options: str) -> str:
    if not options:
        return ""
    decoded = unquote(options)
    match = re.search(r"search_path\s*=\s*([^ ,]+)", decoded, flags=re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1)
    if "," in value:
        value = value.split(",", 1)[0]
    return value.strip()


def build_postgresql_uri(db_config) -> str:
    sslmode = _value_or_none(getattr(db_config, "sslmode", None))
    return str(
        URL.create(
            drivername="postgresql+psycopg2",
            username=_value_or_none(db_config.username),
            password=_value_or_none(db_config.password),
            host=_value_or_none(db_config.host),
            port=_port_or_none(db_config.port),
            database=_value_or_none(db_config.database),
            query={"sslmode": sslmode} if sslmode else {},
        )
    )


def resolve_postgresql_context(db_config, uri: str) -> Tuple[str, str, str, str]:
    url = make_url(uri)
    query_params: Dict[str, str] = {k: _clean_str(v) for k, v in url.query.items()}
    database = _clean_str(url.database) or _clean_str(db_config.database) or "postgres"
    config_schema = _clean_str(getattr(db_config, "schema_name", None) or getattr(db_config, "schema", None))
    schema = (
        query_params.get("currentSchema")
        or query_params.get("schema")
        or _extract_schema_from_pg_options(query_params.get("options", ""))
        or config_schema
        or "public"
    )
    return "postgresql", "", database, schema

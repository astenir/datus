# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""URI builder and context resolver for Oracle."""

from typing import Dict, Optional, Tuple, Union
from urllib.parse import quote, urlencode

from sqlalchemy.engine.url import make_url


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


def _upper_or_none(value: Optional[Union[str, int]]) -> Optional[str]:
    cleaned = _clean_str(value)
    return cleaned.upper() if cleaned else None


def build_oracle_uri(db_config) -> str:
    """Build a SQLAlchemy Oracle URI from adapter config."""
    query: Dict[str, str] = {}
    service_name = _value_or_none(getattr(db_config, "service_name", None))
    if service_name is None and not hasattr(db_config, "service_name"):
        service_name = _value_or_none(getattr(db_config, "database", None))
    sid = _value_or_none(getattr(db_config, "sid", None))
    if service_name:
        query["service_name"] = service_name
    elif sid:
        query["sid"] = sid
    username = quote(_clean_str(db_config.username), safe="")
    password = quote(_clean_str(db_config.password), safe="")
    auth = f"{username}:{password}@" if password else f"{username}@"
    host = _clean_str(db_config.host)
    port = _port_or_none(db_config.port)
    netloc = f"{host}:{port}" if port is not None else host
    query_string = urlencode(query)
    suffix = f"?{query_string}" if query_string else ""
    return f"oracle+oracledb://{auth}{netloc}/{suffix}"


def resolve_oracle_context(db_config, uri: str) -> Tuple[str, str, str, str]:
    """Resolve Datus context tuple from Oracle config and SQLAlchemy URI."""
    url = make_url(uri)
    query_params: Dict[str, str] = {k: _clean_str(v) for k, v in url.query.items()}
    service_name = query_params.get("service_name") or _clean_str(getattr(db_config, "service_name", None))
    sid = query_params.get("sid") or _clean_str(getattr(db_config, "sid", None))
    database = service_name or sid or _clean_str(getattr(db_config, "database", None))
    schema = (
        _upper_or_none(query_params.get("schema"))
        or _upper_or_none(getattr(db_config, "schema_name", None))
        or _upper_or_none(getattr(db_config, "schema", None))
        or _upper_or_none(getattr(db_config, "username", None))
        or ""
    )
    return "oracle", "", database, schema

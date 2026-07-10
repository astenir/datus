"""User-owned private datasource helpers."""

from __future__ import annotations

import re
from dataclasses import asdict
from fnmatch import fnmatchcase
from typing import Any

from datus.configuration.agent_config import DbConfig
from datus.utils.exceptions import DatusException, ErrorCode

DATASOURCE_ID_PREFIX = "personal_"
DATASOURCE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DATASOURCE_TYPE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9_.:@/ -]+$")
CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")

MAX_DISPLAY_NAME_LENGTH = 120
MAX_FIELD_LENGTH = 255
MAX_PASSWORD_LENGTH = 4096


def personal_datasource_key(datasource_id: str) -> str:
    return f"{DATASOURCE_ID_PREFIX}{normalize_datasource_id(datasource_id)}"


def datasource_id_from_key(datasource_key: str) -> str | None:
    if not datasource_key.startswith(DATASOURCE_ID_PREFIX):
        return None
    datasource_id = datasource_key[len(DATASOURCE_ID_PREFIX) :]
    return datasource_id if DATASOURCE_ID_RE.fullmatch(datasource_id) else None


def normalize_datasource_id(value: str) -> str:
    datasource_id = value.strip()
    if not datasource_id or len(datasource_id) > 80 or not DATASOURCE_ID_RE.fullmatch(datasource_id):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal datasource id.")
    return datasource_id


def normalize_datasource_type(value: str) -> str:
    datasource_type = value.strip().lower()
    if not datasource_type or len(datasource_type) > 80 or not DATASOURCE_TYPE_RE.fullmatch(datasource_type):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid datasource type.")
    return datasource_type


def normalize_host(value: str) -> str:
    host = value.strip().lower()
    if not host or len(host) > MAX_FIELD_LENGTH or not HOST_RE.fullmatch(host):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid datasource host.")
    return host


def normalize_port(value: str | int) -> str:
    text = str(value).strip()
    try:
        port = int(text)
    except ValueError as exc:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid datasource port.") from exc
    if port < 1 or port > 65535:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid datasource port.")
    return str(port)


def normalize_required_text(value: str, *, label: str) -> str:
    text = value.strip()
    if not text:
        raise DatusException(ErrorCode.COMMON_FIELD_REQUIRED, message=f"{label} is required.")
    if len(text) > MAX_FIELD_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"{label} is too long.")
    if not NAME_RE.fullmatch(text):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"{label} contains unsupported characters.")
    return text


def normalize_optional_text(value: str | None, *, label: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_DISPLAY_NAME_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"{label} is too long.")
    if not NAME_RE.fullmatch(text):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message=f"{label} contains unsupported characters.")
    return text


def normalize_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_DISPLAY_NAME_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Display name is too long.")
    if CONTROL_CHARACTER_RE.search(text):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Display name contains unsupported characters.")
    return text


def normalize_password(value: str) -> str:
    password = value.strip()
    if not password:
        raise DatusException(ErrorCode.COMMON_FIELD_REQUIRED, message="Password is required.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Password is too long.")
    return password


def personal_datasource_options(agent_config: Any) -> dict[str, Any]:
    raw = {}
    enterprise = getattr(agent_config, "enterprise_config", {}) or {}
    if isinstance(enterprise, dict):
        raw = enterprise.get("user_datasources") or enterprise.get("personal_datasources") or {}
    if not isinstance(raw, dict):
        raw = {}

    allowed_types = _normalized_list(raw.get("allowed_types")) or []
    allowed_hosts = _normalized_list(raw.get("allowed_hosts")) or []
    default_ports = raw.get("default_ports") if isinstance(raw.get("default_ports"), dict) else {}
    return {
        "enabled": bool(raw.get("enabled")) and bool(allowed_types) and bool(allowed_hosts),
        "allowed_types": allowed_types,
        "allowed_hosts": allowed_hosts,
        "default_ports": {str(k).lower(): str(v) for k, v in default_ports.items()},
    }


def validate_personal_datasource_policy(
    agent_config: Any,
    *,
    datasource_type: str,
    host: str,
) -> None:
    options = personal_datasource_options(agent_config)
    if not options["enabled"]:
        raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="Personal datasources are not enabled.")
    if datasource_type not in options["allowed_types"]:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Datasource type is not allowed.")
    if not _host_allowed(host, options["allowed_hosts"]):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Datasource host is not allowed.")


def datasource_record_to_db_config(record: dict[str, Any]) -> DbConfig:
    return DbConfig.filter_kwargs(
        DbConfig,
        {
            "type": str(record["type"]),
            "host": str(record["host"]),
            "port": str(record["port"]),
            "username": str(record["username"]),
            "password": str(record["password"]),
            "database": str(record["database"]),
            "schema": str(record.get("schema") or ""),
            "catalog": str(record.get("catalog") or ""),
            "display_name": str(record.get("display_name") or ""),
            "extra": {"owner": "user"},
        },
    )


def redact_db_config(config: DbConfig) -> dict[str, Any]:
    data = asdict(config)
    data.pop("password", None)
    data.pop("private_key_file_pwd", None)
    return data


def password_hint(password: str) -> str:
    if len(password) <= 4:
        return "***"
    return f"***{password[-4:]}"


def _normalized_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        return []
    return sorted({str(item).strip().lower() for item in raw_values if str(item).strip()})


def _host_allowed(host: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(host, pattern) for pattern in patterns)

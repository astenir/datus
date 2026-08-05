"""Enterprise fail-closed policy for the upstream auth-provider loader."""

from __future__ import annotations

from typing import Any

from datus.api.auth.no_auth_provider import NoAuthProvider
from datus.utils.exceptions import DatusException, ErrorCode


def require_auth_provider_class(enterprise_config: Any, class_path: Any) -> None:
    if _enterprise_enabled(enterprise_config) and not class_path:
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="enterprise.enabled=true requires api.auth_provider.class; NoAuthProvider is local-only.",
        )


def require_auth_provider_instance(enterprise_config: Any, instance: Any) -> None:
    if _enterprise_enabled(enterprise_config) and isinstance(instance, NoAuthProvider):
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="enterprise.enabled=true cannot use NoAuthProvider; configure a production auth provider.",
        )


def _enterprise_enabled(enterprise_config: Any) -> bool:
    raw = enterprise_config or {}
    if not isinstance(raw, dict):
        return False
    value = raw.get("enabled")
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)

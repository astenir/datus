"""Compatibility imports for the enterprise auth-provider loader policy."""

from datus_enterprise.auth.loader_policy import (
    _enterprise_enabled,
    require_auth_provider_class,
    require_auth_provider_instance,
)

__all__ = [
    "_enterprise_enabled",
    "require_auth_provider_class",
    "require_auth_provider_instance",
]

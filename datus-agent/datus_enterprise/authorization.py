"""Compatibility wrappers for enterprise authorization helpers."""

from __future__ import annotations

from datus.api.enterprise import AccessDecision as AuthorizationDecision
from datus.api.enterprise import LocalAuthorizationProvider, ResourceRef, authorize, require_module

__all__ = [
    "AuthorizationDecision",
    "LocalAuthorizationProvider",
    "ResourceRef",
    "authorize",
    "require_module",
]

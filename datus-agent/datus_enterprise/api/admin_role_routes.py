"""Compatibility alias for enterprise role administration routes."""

from __future__ import annotations

import sys

from datus_enterprise.admin_roles import routes as _routes

sys.modules[__name__] = _routes

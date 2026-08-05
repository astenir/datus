"""Compatibility alias for enterprise user administration routes."""

from __future__ import annotations

import sys

from datus_enterprise.admin_users import routes as _routes

sys.modules[__name__] = _routes

"""Compatibility alias for enterprise session administration routes."""

from __future__ import annotations

import sys

from datus_enterprise.admin_sessions import routes as _routes

sys.modules[__name__] = _routes

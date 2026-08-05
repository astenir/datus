"""Compatibility alias for enterprise datasource administration routes."""

from __future__ import annotations

import sys

from datus_enterprise.admin_datasources import routes as _routes

sys.modules[__name__] = _routes

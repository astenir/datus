"""Downstream session scope and project identity helpers."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

SAFE_SESSION_SCOPE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def session_scope_from_user_id(user_id: Optional[str]) -> Optional[str]:
    """Return a filesystem-safe session scope for an authenticated user id.

    Session scopes are path segments, while enterprise user ids may be emails,
    UUID URNs, or IdP subjects. Keep already-safe ids readable and hash anything
    else to avoid path traversal and accidental directory splits.
    """
    if user_id is None:
        return None
    raw = str(user_id).strip()
    if not raw:
        return None
    if SAFE_SESSION_SCOPE_RE.fullmatch(raw):
        return raw
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    if not normalized:
        normalized = "user"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{normalized[:48]}_{digest}"


def project_id_from_config(agent_config: Optional[Any]) -> str:
    """Resolve the session body-store project key from request config."""
    if agent_config is not None:
        project_id = getattr(agent_config, "_session_project_id", None)
        if project_id:
            return str(project_id)
        path_manager = getattr(agent_config, "path_manager", None)
        project_name = getattr(path_manager, "project_name", None)
        if project_name:
            return str(project_name)
        configured = getattr(agent_config, "project_name", None)
        if configured:
            return str(configured)
    return "default"

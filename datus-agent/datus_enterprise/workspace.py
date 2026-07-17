"""Request-scoped private workspace helpers for enterprise Agent execution."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode


def prepare_user_workspace(agent_config: Any, user_id: str) -> Path:
    """Create and return the private workspace for one project/user pair.

    User identifiers are hashed before entering the filesystem layout.  The
    configured Datus home and validated project name remain the authoritative
    server-side namespace; callers cannot submit a workspace path.
    """

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise DatusException(ErrorCode.COMMON_VALIDATION_FAILED, message="AUTH_REQUIRED")

    path_manager = getattr(agent_config, "path_manager", None)
    project_name = str(getattr(agent_config, "project_name", "") or "").strip()
    if path_manager is None or not project_name:
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="Enterprise user workspace requires agent.path_manager and project_name.",
        )

    workspace_base = Path(path_manager.workspace_dir).resolve(strict=False)
    user_segment = hashlib.sha256(normalized_user_id.encode("utf-8")).hexdigest()
    project_workspace = workspace_base / project_name
    user_workspace = project_workspace / user_segment

    for directory in (workspace_base, project_workspace, user_workspace):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    resolved_workspace = user_workspace.resolve(strict=False)
    if resolved_workspace != user_workspace or not resolved_workspace.is_relative_to(workspace_base):
        raise DatusException(
            ErrorCode.COMMON_CONFIG_ERROR,
            message="Enterprise user workspace resolved outside its configured root.",
        )

    # The API process owns these opaque workspace directories.  A restrictive
    # mode also prevents unrelated host users from browsing them; application
    # path checks remain the boundary between requests in this same process.
    os.chmod(project_workspace, 0o700)
    os.chmod(user_workspace, 0o700)
    return resolved_workspace


__all__ = ["prepare_user_workspace"]

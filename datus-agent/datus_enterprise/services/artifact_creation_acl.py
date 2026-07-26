"""Default ACL persistence for newly-created enterprise artifacts."""

from __future__ import annotations

from typing import Any, List, Optional

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


async def create_default_artifact_acl_after_manifest(
    agent_config: Any,
    *,
    artifact_type: str,
    slug: str,
    datasources: Optional[List[str]] = None,
) -> Optional[str]:
    """Persist the default private ACL for a newly-created visual artifact.

    Local-compatible invocations have no ACL store or authenticated user and
    intentionally skip this hook. Enterprise API chat requests attach both to
    the request-scoped ``AgentConfig`` clone before the artifact tools run.
    """

    store = getattr(agent_config, "_artifact_acl_store", None)
    owner_user_id = _request_owner_user_id(agent_config)
    if store is None or not owner_user_id:
        if bool(getattr(agent_config, "_enterprise_enabled", False)):
            return "Enterprise artifact creation requires an ACL store and authenticated owner."
        return None

    try:
        from datus_enterprise.artifact_acl import ensure_default_private_acl

        acl = await ensure_default_private_acl(
            store,
            artifact_type=artifact_type,
            slug=slug,
            owner_user_id=owner_user_id,
            datasources=datasources or [],
        )
        if not isinstance(acl, dict) or str(acl.get("owner_user_id") or "").strip() != owner_user_id:
            return "Artifact slug is already reserved by a different owner."
        return None
    except Exception as exc:
        logger.warning(
            "Failed to create default ACL for %s %s owned by %s: %s",
            artifact_type,
            slug,
            owner_user_id,
            exc,
        )
        return f"Failed to create default artifact ACL: {exc}"


def _request_owner_user_id(agent_config: Any) -> str | None:
    raw_user_id = getattr(agent_config, "_request_user_id", None)
    if raw_user_id:
        return str(raw_user_id).strip() or None
    principal = getattr(agent_config, "principal", None)
    if not isinstance(principal, dict):
        return None
    for key in ("user_id", "sub", "employee_id"):
        value = principal.get(key)
        if value:
            return str(value).strip() or None
    return None

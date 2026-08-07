"""Enterprise projection hooks for the upstream FastAPI application."""

from typing import Any, Iterable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status

from datus.api.enterprise.models import AuditEvent

RouteModule = tuple[str, str]

_ENTERPRISE_ROUTE_OVERRIDES: dict[RouteModule, RouteModule | None] = {
    ("datus.api.routes.cli_routes", "cli"): ("datus_enterprise.api.cli_routes", "enterprise_cli"),
    ("datus.api.routes.database_routes", "database"): (
        "datus_enterprise.api.database_routes",
        "enterprise_database",
    ),
    ("datus.api.routes.table_routes", "table"): ("datus_enterprise.api.table_routes", "enterprise_table"),
    ("datus.api.routes.config_routes", "config"): ("datus_enterprise.api.config_routes", "enterprise_config"),
    ("datus.api.routes.models_routes", "models"): ("datus_enterprise.api.models_routes", "enterprise_models"),
    ("datus.api.routes.mcp_routes", "mcp"): ("datus_enterprise.api.mcp_routes", "enterprise_mcp"),
    ("datus.api.routes.kb_routes", "kb"): ("datus_enterprise.api.kb_routes", "enterprise_kb"),
    ("datus.api.routes.agent_routes", "agent"): ("datus_enterprise.api.legacy_agent_routes", "agent"),
    ("datus.api.routes.success_story_routes", "success_story"): (
        "datus_enterprise.api.success_story_routes",
        "enterprise_success_story",
    ),
    ("datus.api.routes.dashboard_routes", "dashboard"): (
        "datus_enterprise.api.dashboard_routes",
        "enterprise_dashboard",
    ),
    ("datus.api.routes.report_routes", "report"): None,
}

_ENTERPRISE_ROUTE_INSERTIONS: dict[RouteModule, tuple[RouteModule, ...]] = {
    ("datus.api.routes.table_routes", "table"): (("datus.api.routes.subject_routes", "subject"),),
    ("datus.api.routes.dashboard_routes", "dashboard"): (
        ("datus_enterprise.api.me_routes", "enterprise_me"),
        ("datus_enterprise.api.model_credential_routes", "enterprise_model_credentials"),
        ("datus_enterprise.api.personal_datasource_routes", "enterprise_personal_datasources"),
        ("datus_enterprise.api.personal_mcp_routes", "enterprise_personal_mcp"),
        ("datus_enterprise.api.artifact_routes", "enterprise_artifacts"),
        ("datus_enterprise.api.agent_routes", "enterprise_agents"),
        ("datus_enterprise.api.admin_datasource_routes", "enterprise_datasource_admin"),
        ("datus_enterprise.api.admin_audit_routes", "enterprise_audit_admin"),
        ("datus_enterprise.api.admin_session_routes", "enterprise_session_admin"),
        ("datus_enterprise.api.admin_user_routes", "enterprise_user_admin"),
        ("datus_enterprise.api.admin_role_routes", "enterprise_role_admin"),
        ("datus_enterprise.api.admin_quota_routes", "enterprise_quota_admin"),
        ("datus_enterprise.api.admin_secret_routes", "enterprise_secret_admin"),
        ("datus_enterprise.api.system_routes", "enterprise_system"),
    ),
}

_ROUTE_DISABLED_OPERATIONS = {
    "agent": "agent.config_legacy",
    "explorer": "explorer.legacy",
    "visualization": "visualization.legacy",
    "tool": "tools.direct_dispatch",
}

_LEGACY_ENTERPRISE_DISABLED_DETAIL = {
    "errorCode": "ENTERPRISE_LEGACY_API_DISABLED",
    "errorMessage": "Legacy workflow APIs are disabled when enterprise.enabled=true. Use /api/v1 routes.",
}


def project_enterprise_route_modules(upstream_routes: Iterable[RouteModule]) -> list[RouteModule]:
    """Replace authoritative routes and append enterprise-only surfaces."""

    projected: list[RouteModule] = []
    for route in upstream_routes:
        replacement = _ENTERPRISE_ROUTE_OVERRIDES.get(route, route)
        if replacement is not None:
            projected.append(replacement)
        projected.extend(_ENTERPRISE_ROUTE_INSERTIONS.get(route, ()))
    return projected


def include_api_router(app: FastAPI, router: APIRouter, name: str) -> None:
    """Register a route module, applying enterprise legacy gates at the app edge."""

    disabled_operation = _ROUTE_DISABLED_OPERATIONS.get(name)
    if disabled_operation:
        from datus.api.enterprise.deps import require_enterprise_route_disabled

        app.include_router(
            router,
            dependencies=[Depends(require_enterprise_route_disabled(operation=disabled_operation))],
        )
        return
    app.include_router(router)


async def reject_legacy_api_in_enterprise(*, operation: str) -> None:
    """Disable legacy OAuth/workflow endpoints in enterprise mode."""

    from datus.api import deps

    extensions = deps.get_enterprise_extensions()
    if not extensions.enabled:
        return

    await extensions.audit_sink.write(
        AuditEvent(
            user_id=None,
            action="system.route_disabled",
            resource_type="legacy_api",
            resource_id=None,
            decision="deny",
            reason=f"Route operation '{operation}' is disabled in enterprise mode.",
            metadata={"operation": operation},
        )
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LEGACY_ENTERPRISE_DISABLED_DETAIL)


async def get_legacy_current_client(request: Request, *, auth_service: Any) -> str:
    """Authenticate legacy workflow requests after enterprise-mode rejection."""

    await reject_legacy_api_in_enterprise(operation="workflow.legacy")
    raw = request.headers.get("Authorization")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = raw.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_service.validate_token(token.strip())
    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(client_id)

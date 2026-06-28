"""Enterprise security classification for FastAPI routes registered by create_app()."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable

RouteKey = tuple[str, str]

MODULE_RBAC = "module_rbac"
SESSION_OWNER = "session_owner"
DATASOURCE_PROJECTION = "datasource_projection"
DATASOURCE_GRANT = "datasource_grant"
SQL_POLICY = "sql_policy"
TABLE_SCOPE = "table_scope"
ARTIFACT_ACL = "artifact_acl"
PLATFORM_STATUS_GATE = "platform_status_gate"
PLATFORM_STATUS_EXCEPTION = "platform_status_exception"
AUDIT = "audit"
LEGACY_DISABLED = "legacy_disabled"
SYSTEM_READONLY = "system_readonly"
LOCAL_COMPATIBLE = "local_compatible"
MUTATION_EXECUTION = "mutation_execution"
MODEL_POLICY = "model_policy"
QUOTA = "quota"
TOOL_PERMISSION = "tool_permission"

KNOWN_SECURITY_CATEGORIES = frozenset(
    {
        MODULE_RBAC,
        SESSION_OWNER,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        TABLE_SCOPE,
        ARTIFACT_ACL,
        PLATFORM_STATUS_GATE,
        PLATFORM_STATUS_EXCEPTION,
        AUDIT,
        LEGACY_DISABLED,
        SYSTEM_READONLY,
        LOCAL_COMPATIBLE,
        MUTATION_EXECUTION,
        MODEL_POLICY,
        QUOTA,
        TOOL_PERMISSION,
    }
)

DATA_BOUNDARY_CATEGORIES = frozenset(
    {
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        TABLE_SCOPE,
        ARTIFACT_ACL,
    }
)


@dataclass(frozen=True)
class RouteSecurityPolicy:
    """Static enterprise-mode acceptance policy for one registered route."""

    categories: frozenset[str]
    module_permission: str | None = None
    audit_action: str | None = None
    note: str = ""
    data_boundaries: frozenset[str] = field(default_factory=frozenset)


def route_key(method: str, path: str) -> RouteKey:
    return (method.upper(), path)


def _policy(
    *categories: str,
    module_permission: str | None = None,
    audit_action: str | None = None,
    note: str = "",
    data_boundaries: Iterable[str] = (),
) -> RouteSecurityPolicy:
    return RouteSecurityPolicy(
        categories=frozenset(categories),
        module_permission=module_permission,
        audit_action=audit_action,
        note=note,
        data_boundaries=frozenset(data_boundaries),
    )


_ROUTES: dict[RouteKey, RouteSecurityPolicy] = {}


def _add(method: str, path: str, policy: RouteSecurityPolicy) -> None:
    key = route_key(method, path)
    if key in _ROUTES:
        raise RuntimeError(f"Duplicate route security policy for {method} {path}")
    _ROUTES[key] = policy


def _add_many(method: str, paths: Iterable[str], policy: RouteSecurityPolicy) -> None:
    for path in paths:
        _add(method, path, policy)


_LOCAL_READ_POLICY = _policy(
    SYSTEM_READONLY,
    LOCAL_COMPATIBLE,
    note="Unauthenticated local/system status route; does not expose enterprise resources.",
)
_LEGACY_DISABLED_POLICY = _policy(
    LEGACY_DISABLED,
    LOCAL_COMPATIBLE,
    AUDIT,
    audit_action="system.route_disabled",
    note="Compatibility route; enterprise.enabled=true must reject before legacy execution.",
)
_CHAT_READ_POLICY = _policy(
    MODULE_RBAC,
    SESSION_OWNER,
    SYSTEM_READONLY,
    module_permission="module.chat",
    note="Read-only chat/session metadata; session owner checks prevent cross-user access.",
)
_CHAT_ACTIVE_POLICY = _policy(
    MODULE_RBAC,
    SESSION_OWNER,
    PLATFORM_STATUS_GATE,
    MUTATION_EXECUTION,
    module_permission="module.chat",
    audit_action="system.platform_status",
    note="Chat session mutation/control route; active status is required before service execution.",
)
_CHAT_CONTROL_EXCEPTION_POLICY = _policy(
    MODULE_RBAC,
    SESSION_OWNER,
    PLATFORM_STATUS_EXCEPTION,
    MUTATION_EXECUTION,
    module_permission="module.chat",
    note="Operational stop/cancel control remains available during readonly/maintenance.",
)
_CATALOG_READ_POLICY = _policy(
    MODULE_RBAC,
    DATASOURCE_PROJECTION,
    DATASOURCE_GRANT,
    TABLE_SCOPE,
    SYSTEM_READONLY,
    module_permission="module.datasource_catalog",
    data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, TABLE_SCOPE},
)
_ARTIFACT_DASHBOARD_VIEW_POLICY = _policy(
    MODULE_RBAC,
    ARTIFACT_ACL,
    SYSTEM_READONLY,
    module_permission="module.dashboard.view",
    data_boundaries={ARTIFACT_ACL},
)
_ARTIFACT_REPORT_VIEW_POLICY = _policy(
    MODULE_RBAC,
    ARTIFACT_ACL,
    SYSTEM_READONLY,
    module_permission="module.report.view",
    data_boundaries={ARTIFACT_ACL},
)

_add("GET", "/", _LOCAL_READ_POLICY)
_add("GET", "/health", _LOCAL_READ_POLICY)
_add_many("POST", ["/auth/token", "/workflows/run", "/workflows/feedback"], _LEGACY_DISABLED_POLICY)

_add(
    "POST",
    "/api/v1/chat/stream",
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        MODEL_POLICY,
        QUOTA,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.chat",
        audit_action="chat.stream",
        data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, SQL_POLICY},
    ),
)
_add(
    "POST",
    "/api/v1/chat/feedback",
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        MODEL_POLICY,
        QUOTA,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.chat",
        audit_action="chat.feedback",
        data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, SQL_POLICY},
    ),
)
_add_many(
    "POST",
    [
        "/api/v1/chat/resume",
        "/api/v1/chat/sessions/{session_id}/compact",
        "/api/v1/chat/user_interaction",
        "/api/v1/chat/insert",
        "/api/v1/chat/tool_result",
    ],
    _CHAT_ACTIVE_POLICY,
)
_add("POST", "/api/v1/chat/stop", _CHAT_CONTROL_EXCEPTION_POLICY)
_add_many("GET", ["/api/v1/chat/sessions", "/api/v1/chat/history"], _CHAT_READ_POLICY)
_add("DELETE", "/api/v1/chat/sessions/{session_id}", _CHAT_ACTIVE_POLICY)

_add(
    "POST",
    "/api/v1/sql/execute",
    _policy(
        MODULE_RBAC,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        QUOTA,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.sql_executor",
        audit_action="sql.execute",
        data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, SQL_POLICY},
    ),
)
_add(
    "POST",
    "/api/v1/sql/stop_execute",
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        PLATFORM_STATUS_EXCEPTION,
        MUTATION_EXECUTION,
        module_permission="module.sql_executor",
        note="Stop operation is an explicit maintenance control exception.",
    ),
)
_add(
    "POST",
    "/api/v1/context/{context_type}",
    _policy(
        MODULE_RBAC,
        SYSTEM_READONLY,
        module_permission="module.datasource_catalog",
        note="Only datasource metadata-producing context commands require catalog permission.",
    ),
)
_add(
    "POST",
    "/api/v1/internal/{command}",
    _policy(
        MODULE_RBAC,
        SYSTEM_READONLY,
        note="Command-specific RBAC: datasource metadata commands require module.datasource_catalog; "
        "chat session commands require module.chat.",
    ),
)

_add("GET", "/api/v1/catalog/list", _CATALOG_READ_POLICY)
_add_many("GET", ["/api/v1/table/detail", "/api/v1/semantic_model"], _CATALOG_READ_POLICY)
_add(
    "POST",
    "/api/v1/semantic_model",
    _policy(
        MODULE_RBAC,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        TABLE_SCOPE,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.config.edit",
        audit_action="semantic_model.save",
        data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, TABLE_SCOPE},
    ),
)
_add(
    "POST",
    "/api/v1/semantic_model/validate",
    _policy(
        MODULE_RBAC,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        TABLE_SCOPE,
        SYSTEM_READONLY,
        module_permission="module.config.edit",
        data_boundaries={DATASOURCE_PROJECTION, DATASOURCE_GRANT, TABLE_SCOPE},
        note="Validation does not persist metadata but must respect table authorization.",
    ),
)

_add_many(
    "GET",
    [
        "/api/v1/subject/list",
        "/api/v1/agent/use_tools",
        "/api/v1/agent",
        "/api/v1/agent/list",
        "/api/v1/agent/tools",
    ],
    _LEGACY_DISABLED_POLICY,
)
_add_many(
    "POST",
    [
        "/api/v1/subject/create",
        "/api/v1/subject/rename",
        "/api/v1/subject/metric",
        "/api/v1/subject/metric/dimensions",
        "/api/v1/subject/metric/preview",
        "/api/v1/subject/reference_sql",
        "/api/v1/subject/reference_sql/create",
        "/api/v1/subject/reference_sql/edit",
        "/api/v1/subject/metric/create",
        "/api/v1/subject/metric/edit",
        "/api/v1/subject/semantic_model/edit",
        "/api/v1/agent/create",
        "/api/v1/agent/edit",
        "/api/v1/data_visualization",
        "/api/v1/tools/{tool_name}",
        "/api/v1/success-stories",
    ],
    _LEGACY_DISABLED_POLICY,
)
_add_many("DELETE", ["/api/v1/subject/delete", "/api/v1/agent/delete"], _LEGACY_DISABLED_POLICY)

_add(
    "GET",
    "/api/v1/config/agent",
    _policy(MODULE_RBAC, SYSTEM_READONLY, module_permission="module.config.view"),
)
_add_many(
    "PUT",
    ["/api/v1/config/datasources", "/api/v1/config/models"],
    _policy(
        MODULE_RBAC,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.config.edit",
        audit_action="system.platform_status",
    ),
)
_add_many(
    "POST",
    ["/api/v1/config/models/test", "/api/v1/config/datasources/test"],
    _policy(
        MODULE_RBAC,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.config.edit",
        note="Connectivity probes can reach external systems and are blocked outside active status.",
    ),
)
_add(
    "GET",
    "/api/v1/models",
    _policy(MODULE_RBAC, MODEL_POLICY, SYSTEM_READONLY, module_permission="module.config.view"),
)

_add_many(
    "GET",
    [
        "/api/v1/mcp/servers",
        "/api/v1/mcp/servers/{server_name}/tools",
        "/api/v1/mcp/servers/{server_name}/filters",
    ],
    _policy(MODULE_RBAC, TOOL_PERMISSION, SYSTEM_READONLY, module_permission="module.mcp"),
)
_add(
    "GET",
    "/api/v1/mcp/servers/{server_name}/connectivity",
    _policy(MODULE_RBAC, TOOL_PERMISSION, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.mcp"),
)
_add_many(
    "POST",
    ["/api/v1/mcp/servers", "/api/v1/mcp/servers/{server_name}/tools/{tool_name}/call"],
    _policy(MODULE_RBAC, TOOL_PERMISSION, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.mcp"),
)
_add_many(
    "PUT",
    ["/api/v1/mcp/servers/{server_name}/filters"],
    _policy(MODULE_RBAC, TOOL_PERMISSION, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.mcp"),
)
_add_many(
    "DELETE",
    ["/api/v1/mcp/servers/{server_name}", "/api/v1/mcp/servers/{server_name}/filters"],
    _policy(MODULE_RBAC, TOOL_PERMISSION, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.mcp"),
)

_add_many(
    "POST",
    ["/api/v1/kb/bootstrap", "/api/v1/kb/bootstrap-docs"],
    _policy(MODULE_RBAC, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.kb"),
)
_add_many(
    "POST",
    ["/api/v1/kb/bootstrap/{stream_id}/cancel", "/api/v1/kb/bootstrap-docs/{stream_id}/cancel"],
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        PLATFORM_STATUS_EXCEPTION,
        MUTATION_EXECUTION,
        module_permission="module.kb",
        note="Cancel operation is an explicit maintenance control exception and is bound to the stream owner.",
    ),
)

_add("GET", "/api/v1/dashboard/detail", _ARTIFACT_DASHBOARD_VIEW_POLICY)
_add(
    "POST",
    "/api/v1/dashboard/query",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        DATASOURCE_PROJECTION,
        DATASOURCE_GRANT,
        SQL_POLICY,
        QUOTA,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.dashboard.query",
        audit_action="dashboard.query",
        data_boundaries={ARTIFACT_ACL, DATASOURCE_PROJECTION, DATASOURCE_GRANT, SQL_POLICY},
    ),
)
_add("GET", "/api/v1/report/detail", _ARTIFACT_REPORT_VIEW_POLICY)

_add_many(
    "GET",
    ["/api/v1/me", "/api/v1/me/permissions", "/api/v1/me/features"],
    _policy(SYSTEM_READONLY, note="Current-user capability view based on authenticated AppContext."),
)
_add(
    "GET",
    "/api/v1/me/datasource-grants",
    _policy(DATASOURCE_GRANT, SYSTEM_READONLY, data_boundaries={DATASOURCE_GRANT}),
)
_add(
    "GET",
    "/api/v1/me/sessions",
    _policy(SESSION_OWNER, SYSTEM_READONLY, note="Lists only the current user's sessions."),
)
_add("GET", "/api/v1/me/usage", _policy(QUOTA, SYSTEM_READONLY))

_add_many(
    "GET",
    ["/api/v1/dashboards", "/api/v1/dashboards/{slug}", "/api/v1/dashboards/{slug}/html"],
    _ARTIFACT_DASHBOARD_VIEW_POLICY,
)
_add(
    "GET",
    "/api/v1/dashboards/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        SYSTEM_READONLY,
        module_permission="module.dashboard.view",
        audit_action="artifact.share",
        data_boundaries={ARTIFACT_ACL},
        note="Creator/admin self-service sharing state; owner check is enforced through artifact ACL.",
    ),
)
_add(
    "PUT",
    "/api/v1/dashboards/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.dashboard.view",
        audit_action="artifact.share",
        data_boundaries={ARTIFACT_ACL},
        note="Creator/admin self-service sharing mutation; owner check is enforced through artifact ACL.",
    ),
)
_add_many(
    "GET", ["/api/v1/reports", "/api/v1/reports/{slug}", "/api/v1/reports/{slug}/html"], _ARTIFACT_REPORT_VIEW_POLICY
)
_add(
    "GET",
    "/api/v1/reports/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        SYSTEM_READONLY,
        module_permission="module.report.view",
        audit_action="artifact.share",
        data_boundaries={ARTIFACT_ACL},
        note="Creator/admin self-service sharing state; owner check is enforced through artifact ACL.",
    ),
)
_add(
    "PUT",
    "/api/v1/reports/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.report.view",
        audit_action="artifact.share",
        data_boundaries={ARTIFACT_ACL},
        note="Creator/admin self-service sharing mutation; owner check is enforced through artifact ACL.",
    ),
)
_add(
    "GET",
    "/api/v1/admin/artifacts",
    _policy(MODULE_RBAC, ARTIFACT_ACL, AUDIT, SYSTEM_READONLY, module_permission="module.admin.artifacts"),
)
_add(
    "GET",
    "/api/v1/admin/artifacts/{artifact_type}/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        SYSTEM_READONLY,
        module_permission="module.admin.artifacts",
        data_boundaries={ARTIFACT_ACL},
    ),
)
_add(
    "PUT",
    "/api/v1/admin/artifacts/{artifact_type}/{slug}/acl",
    _policy(
        MODULE_RBAC,
        ARTIFACT_ACL,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.admin.artifacts",
        audit_action="admin.artifacts.acl.update",
        data_boundaries={ARTIFACT_ACL},
    ),
)

_add_many(
    "GET",
    [
        "/api/v1/admin/datasources",
        "/api/v1/admin/datasource-grants",
        "/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    ],
    _policy(MODULE_RBAC, DATASOURCE_GRANT, SYSTEM_READONLY, module_permission="module.admin.datasources"),
)
_add_many(
    "PUT",
    [
        "/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
        "/api/v1/admin/datasource-default",
    ],
    _policy(
        MODULE_RBAC,
        DATASOURCE_GRANT,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.admin.datasources",
        data_boundaries={DATASOURCE_GRANT},
    ),
)
_add(
    "DELETE",
    "/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
    _policy(
        MODULE_RBAC,
        DATASOURCE_GRANT,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.admin.datasources",
        data_boundaries={DATASOURCE_GRANT},
    ),
)

_add(
    "GET",
    "/api/v1/admin/audit-logs",
    _policy(MODULE_RBAC, AUDIT, SYSTEM_READONLY, module_permission="module.admin.audit"),
)
_add(
    "GET",
    "/api/v1/admin/audit-logs/export",
    _policy(
        MODULE_RBAC,
        AUDIT,
        QUOTA,
        PLATFORM_STATUS_EXCEPTION,
        MUTATION_EXECUTION,
        module_permission="module.admin.audit.export",
        audit_action="admin.audit.export",
        note="Audit export is read-only but high-impact; quota and audit are required while readonly remains allowed.",
    ),
)

_add_many(
    "GET",
    ["/api/v1/admin/sessions", "/api/v1/admin/sessions/{session_id}"],
    _policy(MODULE_RBAC, SESSION_OWNER, AUDIT, SYSTEM_READONLY, module_permission="module.admin.sessions"),
)
_add(
    "POST",
    "/api/v1/admin/sessions/{session_id}/stop",
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        AUDIT,
        PLATFORM_STATUS_EXCEPTION,
        MUTATION_EXECUTION,
        module_permission="module.admin.sessions",
        note="Admin stop remains available in maintenance windows.",
    ),
)
_add(
    "DELETE",
    "/api/v1/admin/sessions/{session_id}",
    _policy(
        MODULE_RBAC,
        SESSION_OWNER,
        AUDIT,
        PLATFORM_STATUS_GATE,
        MUTATION_EXECUTION,
        module_permission="module.admin.sessions",
    ),
)

_add_many(
    "GET",
    ["/api/v1/admin/users", "/api/v1/admin/users/{user_id}"],
    _policy(MODULE_RBAC, AUDIT, SYSTEM_READONLY, module_permission="module.admin.users"),
)
_add(
    "PUT",
    "/api/v1/admin/users/{user_id}",
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.users"),
)
_add_many(
    "POST",
    ["/api/v1/admin/users/{user_id}/disable", "/api/v1/admin/users/{user_id}/enable"],
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.users"),
)

_add_many(
    "GET",
    ["/api/v1/admin/roles", "/api/v1/admin/roles/{role_id}", "/api/v1/admin/users/{user_id}/roles"],
    _policy(MODULE_RBAC, AUDIT, SYSTEM_READONLY, module_permission="module.admin.roles"),
)
_add_many(
    "PUT",
    [
        "/api/v1/admin/roles/{role_id}",
        "/api/v1/admin/roles/{role_id}/permissions",
        "/api/v1/admin/users/{user_id}/roles",
    ],
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.roles"),
)
_add(
    "DELETE",
    "/api/v1/admin/roles/{role_id}",
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.roles"),
)

_add_many(
    "GET",
    ["/api/v1/admin/quotas", "/api/v1/admin/usage"],
    _policy(MODULE_RBAC, QUOTA, SYSTEM_READONLY, module_permission="module.admin.quotas"),
)
_add(
    "PUT",
    "/api/v1/admin/quotas",
    _policy(
        MODULE_RBAC, QUOTA, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.quotas"
    ),
)

_add_many(
    "GET",
    ["/api/v1/admin/secrets", "/api/v1/admin/secrets/{name:path}"],
    _policy(MODULE_RBAC, AUDIT, SYSTEM_READONLY, module_permission="module.admin.secrets"),
)
_add(
    "PUT",
    "/api/v1/admin/secrets/{name:path}",
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.secrets"),
)
_add(
    "DELETE",
    "/api/v1/admin/secrets/{name:path}",
    _policy(MODULE_RBAC, AUDIT, PLATFORM_STATUS_GATE, MUTATION_EXECUTION, module_permission="module.admin.secrets"),
)

_add(
    "GET",
    "/api/v1/system/status",
    _policy(MODULE_RBAC, SYSTEM_READONLY, module_permission="module.system.status"),
)

ROUTE_SECURITY_MATRIX = MappingProxyType(_ROUTES)

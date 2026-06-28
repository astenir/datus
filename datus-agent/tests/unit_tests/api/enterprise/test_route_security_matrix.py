"""Regression checks for the enterprise route security coverage matrix."""

import argparse

from fastapi.routing import APIRoute

from datus.api.enterprise.route_security_matrix import (
    ARTIFACT_ACL,
    AUDIT,
    DATA_BOUNDARY_CATEGORIES,
    DATASOURCE_GRANT,
    KNOWN_SECURITY_CATEGORIES,
    LEGACY_DISABLED,
    LOCAL_COMPATIBLE,
    MODULE_RBAC,
    MUTATION_EXECUTION,
    PLATFORM_STATUS_EXCEPTION,
    PLATFORM_STATUS_GATE,
    ROUTE_SECURITY_MATRIX,
    SYSTEM_READONLY,
    route_key,
)
from datus.api.service import create_app


def _create_app_route_keys() -> set[tuple[str, str]]:
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    keys = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                keys.add(route_key(method, route.path))
    return keys


def test_all_create_app_routes_have_enterprise_security_classification():
    registered = _create_app_route_keys()
    classified = set(ROUTE_SECURITY_MATRIX)

    assert classified == registered


def test_route_security_categories_are_known_and_cover_required_dimensions():
    seen_categories = set()
    for policy in ROUTE_SECURITY_MATRIX.values():
        assert policy.categories
        assert policy.categories <= KNOWN_SECURITY_CATEGORIES
        assert policy.data_boundaries <= DATA_BOUNDARY_CATEGORIES
        seen_categories.update(policy.categories)

    assert {
        MODULE_RBAC,
        "session_owner",
        "datasource_projection",
        ARTIFACT_ACL,
        PLATFORM_STATUS_GATE,
        AUDIT,
        LEGACY_DISABLED,
        SYSTEM_READONLY,
        LOCAL_COMPATIBLE,
    } <= seen_categories


def test_mutation_and_execution_routes_declare_platform_status_gate_or_exception():
    for key, policy in ROUTE_SECURITY_MATRIX.items():
        method, path = key
        is_mutating_http_method = method in {"POST", "PUT", "DELETE"}
        is_local_or_legacy = bool(policy.categories & {LEGACY_DISABLED, LOCAL_COMPATIBLE})
        is_readonly_post_shape = SYSTEM_READONLY in policy.categories and MUTATION_EXECUTION not in policy.categories
        if (
            not (is_mutating_http_method or MUTATION_EXECUTION in policy.categories)
            or is_local_or_legacy
            or is_readonly_post_shape
        ):
            continue

        assert MUTATION_EXECUTION in policy.categories, f"{method} {path} is not classified as mutation/execution"
        assert policy.categories & {PLATFORM_STATUS_GATE, PLATFORM_STATUS_EXCEPTION}, (
            f"{method} {path} lacks platform status gate or explicit exception"
        )


def test_datasource_sql_dashboard_table_and_semantic_routes_declare_execution_boundary():
    data_route_tokens = (
        "/catalog/",
        "/datasource",
        "/sql/",
        "/dashboard",
        "/dashboards",
        "/report",
        "/reports",
        "/table/",
        "/semantic_model",
    )
    for (method, path), policy in ROUTE_SECURITY_MATRIX.items():
        if LEGACY_DISABLED in policy.categories or not path.startswith("/api/v1"):
            continue
        if path in {"/api/v1/sql/stop_execute"} or path.startswith("/api/v1/config/datasources"):
            continue
        if not any(token in path for token in data_route_tokens):
            continue

        assert policy.categories & DATA_BOUNDARY_CATEGORIES or policy.data_boundaries, (
            f"{method} {path} lacks datasource/artifact/SQL/table execution boundary classification"
        )


def test_legacy_disabled_routes_are_audited_and_not_mixed_with_live_enterprise_policy():
    legacy_routes = {
        key: policy for key, policy in ROUTE_SECURITY_MATRIX.items() if LEGACY_DISABLED in policy.categories
    }

    assert legacy_routes
    for key, policy in legacy_routes.items():
        assert AUDIT in policy.categories, f"{key} legacy disable path must be audited"
        assert policy.audit_action == "system.route_disabled"
        assert MODULE_RBAC not in policy.categories
        assert PLATFORM_STATUS_GATE not in policy.categories


def test_admin_mutation_routes_use_module_rbac_and_platform_status_gate():
    admin_mutation_permissions = {
        "module.admin.artifacts",
        "module.admin.datasources",
        "module.admin.quotas",
        "module.admin.roles",
        "module.admin.secrets",
        "module.admin.sessions",
        "module.admin.users",
    }
    for (method, path), policy in ROUTE_SECURITY_MATRIX.items():
        if not path.startswith("/api/v1/admin/") or method not in {"POST", "PUT", "DELETE"}:
            continue
        if PLATFORM_STATUS_EXCEPTION in policy.categories:
            continue

        assert MODULE_RBAC in policy.categories
        assert PLATFORM_STATUS_GATE in policy.categories
        assert policy.module_permission in admin_mutation_permissions


def test_datasource_grant_admin_routes_carry_datasource_boundary():
    for (method, path), policy in ROUTE_SECURITY_MATRIX.items():
        if "/admin/datasource" not in path:
            continue

        assert DATASOURCE_GRANT in policy.categories
        assert MODULE_RBAC in policy.categories
        assert policy.module_permission == "module.admin.datasources"

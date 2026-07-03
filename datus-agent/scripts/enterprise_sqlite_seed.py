#!/usr/bin/env python3
"""Seed single-node enterprise SQLite metadata for RBAC bootstrap."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from datus.api.enterprise.defaults import (
    SqliteEnterpriseDatasourceGrantStore,
    SqliteEnterpriseRoleStore,
    SqliteEnterpriseUserStore,
)

DEFAULT_ADMIN_PERMISSIONS = [
    "module.chat",
    "module.datasource_catalog",
    "module.sql_executor",
    "module.config.view",
    "module.config.edit",
    "module.admin.users",
    "module.admin.roles",
    "module.admin.datasources",
    "module.admin.sessions",
    "module.admin.artifacts",
    "module.admin.audit",
    "module.admin.audit.export",
    "module.admin.quotas",
    "module.admin.secrets",
    "module.admin.agents",
    "module.system.status",
]
DEFAULT_USER_PERMISSIONS = [
    "module.chat",
    "module.datasource_catalog",
    "module.config.view",
    "module.system.status",
]


def _csv_or_repeated(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item and item not in items:
                items.append(item)
    return items


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed SQLite enterprise stores with an admin role, a default user role, and optional grants."
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("DATUS_ENTERPRISE_DB", ".datus/enterprise.db"),
        help="SQLite enterprise metadata DB path. Defaults to DATUS_ENTERPRISE_DB or .datus/enterprise.db.",
    )
    parser.add_argument(
        "--datasource",
        action="append",
        default=None,
        help="Datasource key to grant to the default role. Repeat or comma-separate.",
    )
    parser.add_argument(
        "--admin-datasource",
        action="append",
        default=None,
        help="Datasource key to grant to the admin role. Repeat or comma-separate. Defaults to *.",
    )
    parser.add_argument(
        "--schema", action="append", default=None, help="Default role allowed schema pattern. Repeat or comma-separate."
    )
    parser.add_argument(
        "--table", action="append", default=None, help="Default role allowed table pattern. Repeat or comma-separate."
    )
    parser.add_argument("--admin-user", default="alice", help="Initial admin user id.")
    parser.add_argument("--admin-email", default=None, help="Initial admin email.")
    parser.add_argument("--admin-display-name", default=None, help="Initial admin display name.")
    parser.add_argument("--admin-role", default="enterprise_admin", help="Initial admin role id.")
    parser.add_argument("--admin-role-name", default="Enterprise Admin", help="Initial admin role name.")
    parser.add_argument(
        "--admin-permission",
        action="append",
        default=None,
        help="Admin permission key. Repeat or comma-separate. Defaults to explicit module permissions.",
    )
    parser.add_argument("--default-role", default="employee_basic", help="Default auto-provision role id.")
    parser.add_argument("--default-role-name", default="Employee Basic", help="Default auto-provision role name.")
    parser.add_argument(
        "--default-permission",
        action="append",
        default=None,
        help="Default role permission key. Repeat or comma-separate.",
    )
    parser.add_argument(
        "--skip-default-role",
        action="store_true",
        help="Only seed the admin user/role; do not create a default auto-provision role.",
    )
    parser.add_argument(
        "--default-allow-sql",
        action="store_true",
        help="Allow SQL execution in datasource grants for the default role. Default role is catalog-only otherwise.",
    )
    return parser


async def _seed(args: argparse.Namespace) -> dict[str, Any]:
    db_path = str(Path(args.db_path).expanduser())
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    admin_datasources = _csv_or_repeated(args.admin_datasource) or ["*"]
    default_datasources = _csv_or_repeated(args.datasource)
    schemas = _csv_or_repeated(args.schema) or ["*"]
    tables = _csv_or_repeated(args.table) or ["*"]
    admin_permissions = _csv_or_repeated(args.admin_permission) or DEFAULT_ADMIN_PERMISSIONS
    default_permissions = _csv_or_repeated(args.default_permission) or DEFAULT_USER_PERMISSIONS

    user_store = SqliteEnterpriseUserStore(db_path)
    role_store = SqliteEnterpriseRoleStore(db_path)
    grant_store = SqliteEnterpriseDatasourceGrantStore(db_path)

    admin_role = await role_store.upsert_role(
        role_id=args.admin_role,
        name=args.admin_role_name,
        description="Initial enterprise administrator role",
        permissions=admin_permissions,
        built_in=True,
    )
    default_role = None
    if not args.skip_default_role:
        default_role = await role_store.upsert_role(
            role_id=args.default_role,
            name=args.default_role_name,
            description="Low-privilege role for first-login auto-provisioning",
            permissions=default_permissions,
            built_in=True,
        )

    admin_user = await user_store.upsert_user(
        user_id=args.admin_user,
        display_name=args.admin_display_name or args.admin_user,
        email=args.admin_email,
        enabled=True,
    )
    admin_roles = await role_store.set_user_roles(args.admin_user, [args.admin_role])

    datasource_grants: list[dict[str, Any]] = []
    admin_scope = {
        "allow_catalog": True,
        "allow_sql": True,
        "schemas": ["*"],
        "tables": ["*"],
    }
    default_scope = {
        "allow_catalog": True,
        "allow_sql": bool(args.default_allow_sql),
        "schemas": schemas,
        "tables": tables,
    }
    for datasource in admin_datasources:
        datasource_grants.append(
            await grant_store.put_grant(
                subject_type="role",
                subject_id=args.admin_role,
                datasource_key=datasource,
                effect="allow",
                scope=admin_scope,
            )
        )
    for datasource in default_datasources:
        if default_role is not None:
            datasource_grants.append(
                await grant_store.put_grant(
                    subject_type="role",
                    subject_id=args.default_role,
                    datasource_key=datasource,
                    effect="allow",
                    scope=default_scope,
                )
            )

    return {
        "db_path": db_path,
        "users": [admin_user],
        "roles": [item for item in [admin_role, default_role] if item is not None],
        "user_roles": {args.admin_user: admin_roles},
        "datasource_grants": datasource_grants,
        "auto_provisioning_config": (
            {
                "enabled": True,
                "default_role_ids": [args.default_role],
            }
            if default_role is not None
            else {
                "enabled": False,
                "default_role_ids": [],
            }
        ),
    }


def main() -> None:
    args = _build_parser().parse_args()
    result = asyncio.run(_seed(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

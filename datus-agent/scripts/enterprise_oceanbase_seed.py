#!/usr/bin/env python3
"""Seed OceanBase MySQL enterprise metadata for RBAC bootstrap."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from datus_enterprise.oceanbase_stores import (
    ObEnterpriseDatasourceGrantStore,
    ObEnterpriseRoleStore,
    ObEnterpriseUserStore,
)

DEFAULT_ADMIN_PERMISSIONS = ["*"]
DEFAULT_READER_PERMISSIONS = [
    "module.chat",
    "module.datasource_catalog",
    "module.sql_executor",
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
        description="Seed OceanBase enterprise stores with admin/user roles and datasource grants."
    )
    parser.add_argument("--host", default=os.getenv("DATUS_ENTERPRISE_OB_HOST", ""), help="OceanBase host.")
    parser.add_argument(
        "--port",
        default=os.getenv("DATUS_ENTERPRISE_OB_PORT", "2881"),
        help="OceanBase MySQL port. Defaults to DATUS_ENTERPRISE_OB_PORT or 2881.",
    )
    parser.add_argument("--user", default=os.getenv("DATUS_ENTERPRISE_OB_USER", ""), help="OceanBase user.")
    parser.add_argument(
        "--password",
        default=os.getenv("DATUS_ENTERPRISE_OB_PASSWORD"),
        help="OceanBase password. Defaults to DATUS_ENTERPRISE_OB_PASSWORD.",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("DATUS_ENTERPRISE_OB_DATABASE", "datus_enterprise"),
        help="OceanBase database. Defaults to DATUS_ENTERPRISE_OB_DATABASE or datus_enterprise.",
    )
    parser.add_argument(
        "--pool-max-size",
        default="1",
        help="Connection pool max size for each metadata store. Defaults to 1.",
    )
    parser.add_argument("--datasource", default="ccks_fund", help="Datasource key to grant to the reader role.")
    parser.add_argument(
        "--admin-datasource",
        action="append",
        default=None,
        help="Datasource key to grant to the admin role. Repeat or comma-separate. Defaults to *.",
    )
    parser.add_argument(
        "--schema", action="append", default=None, help="Reader role allowed schema pattern. Repeat or comma-separate."
    )
    parser.add_argument(
        "--table", action="append", default=None, help="Reader role allowed table pattern. Repeat or comma-separate."
    )
    parser.add_argument("--admin-user", default="alice", help="Admin test user id.")
    parser.add_argument("--reader-user", default="bob", help="Reader test user id.")
    parser.add_argument("--admin-role", default="local_admin", help="Admin role id.")
    parser.add_argument("--reader-role", default="fund_reader", help="Reader role id.")
    parser.add_argument("--admin-email", default=None, help="Admin test user email.")
    parser.add_argument("--reader-email", default="bob@example.com", help="Reader test user email.")
    parser.add_argument(
        "--admin-permission",
        action="append",
        default=None,
        help="Admin permission key. Repeat or comma-separate. Defaults to *.",
    )
    parser.add_argument(
        "--reader-permission",
        action="append",
        default=None,
        help="Reader permission key. Repeat or comma-separate.",
    )
    parser.add_argument(
        "--skip-reader-grant",
        action="store_true",
        help="Do not grant the reader role datasource access.",
    )
    return parser


def _store_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    if not str(args.host or "").strip():
        raise SystemExit("OceanBase host is required. Set DATUS_ENTERPRISE_OB_HOST or pass --host.")
    if not str(args.user or "").strip():
        raise SystemExit("OceanBase user is required. Set DATUS_ENTERPRISE_OB_USER or pass --user.")
    if args.password is None:
        raise SystemExit("OceanBase password is required. Set DATUS_ENTERPRISE_OB_PASSWORD or pass --password.")
    return {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": args.database,
        "pool_max_size": args.pool_max_size,
    }


async def _seed(args: argparse.Namespace) -> dict[str, Any]:
    admin_datasources = _csv_or_repeated(args.admin_datasource) or ["*"]
    reader_schemas = _csv_or_repeated(args.schema) or ["public"]
    tables = _csv_or_repeated(args.table) or ["*"]
    admin_permissions = _csv_or_repeated(args.admin_permission) or DEFAULT_ADMIN_PERMISSIONS
    reader_permissions = _csv_or_repeated(args.reader_permission) or DEFAULT_READER_PERMISSIONS

    kwargs = _store_kwargs(args)
    user_store = ObEnterpriseUserStore(**kwargs)
    role_store = ObEnterpriseRoleStore(**kwargs)
    grant_store = ObEnterpriseDatasourceGrantStore(**kwargs)
    stores = [user_store, role_store, grant_store]

    try:
        admin_user = await user_store.upsert_user(
            user_id=args.admin_user,
            display_name=args.admin_user.title(),
            email=args.admin_email,
            enabled=True,
        )
        reader_user = await user_store.upsert_user(
            user_id=args.reader_user,
            display_name=args.reader_user.title(),
            email=args.reader_email,
            enabled=True,
        )

        admin_role = await role_store.upsert_role(
            role_id=args.admin_role,
            name="Local Admin",
            description="Local enterprise test administrator",
            permissions=admin_permissions,
            built_in=True,
        )
        reader_role = await role_store.upsert_role(
            role_id=args.reader_role,
            name="Fund Reader",
            description="Local enterprise reader role",
            permissions=reader_permissions,
            built_in=False,
        )

        admin_roles = await role_store.set_user_roles(args.admin_user, [args.admin_role])
        reader_roles = await role_store.set_user_roles(args.reader_user, [args.reader_role])

        admin_scope = {
            "allow_catalog": True,
            "allow_sql": True,
            "schemas": ["*"],
            "tables": ["*"],
        }
        reader_scope = {
            "allow_catalog": True,
            "allow_sql": True,
            "schemas": reader_schemas,
            "tables": tables,
        }
        grants = []
        for datasource in admin_datasources:
            grants.append(
                await grant_store.put_grant(
                    subject_type="role",
                    subject_id=args.admin_role,
                    datasource_key=datasource,
                    effect="allow",
                    scope=admin_scope,
                )
            )
        if not args.skip_reader_grant:
            grants.append(
                await grant_store.put_grant(
                    subject_type="role",
                    subject_id=args.reader_role,
                    datasource_key=args.datasource,
                    effect="allow",
                    scope=reader_scope,
                )
            )

        return {
            "database": args.database,
            "users": [admin_user, reader_user],
            "roles": [admin_role, reader_role],
            "user_roles": {
                args.admin_user: admin_roles,
                args.reader_user: reader_roles,
            },
            "datasource_grants": grants,
        }
    finally:
        for store in stores:
            await store.close()


def main() -> None:
    args = _build_parser().parse_args()
    result = asyncio.run(_seed(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Seed local enterprise PostgreSQL metadata for manual RBAC testing."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from datus_enterprise.postgres_stores import (
    PgEnterpriseDatasourceGrantStore,
    PgEnterpriseRoleStore,
    PgEnterpriseUserStore,
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
        description="Seed local enterprise PostgreSQL stores with admin/user roles and datasource grants."
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv("DATUS_ENTERPRISE_PG_DSN", ""),
        help="PostgreSQL DSN. Defaults to DATUS_ENTERPRISE_PG_DSN.",
    )
    parser.add_argument("--datasource", default="ccks_fund", help="Datasource key to grant.")
    parser.add_argument(
        "--schema", action="append", default=None, help="Allowed schema pattern. Repeat or comma-separate."
    )
    parser.add_argument(
        "--table", action="append", default=None, help="Allowed table pattern. Repeat or comma-separate."
    )
    parser.add_argument("--admin-user", default="alice", help="Admin test user id.")
    parser.add_argument("--reader-user", default="bob", help="Reader test user id.")
    parser.add_argument("--admin-role", default="local_admin", help="Admin role id.")
    parser.add_argument("--reader-role", default="fund_reader", help="Reader role id.")
    parser.add_argument("--admin-email", default="alice@example.com", help="Admin test user email.")
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


async def _seed(args: argparse.Namespace) -> dict[str, Any]:
    if not args.dsn.strip():
        raise SystemExit("PostgreSQL DSN is required. Set DATUS_ENTERPRISE_PG_DSN or pass --dsn.")

    schemas = _csv_or_repeated(args.schema) or ["public"]
    tables = _csv_or_repeated(args.table) or ["*"]
    admin_permissions = _csv_or_repeated(args.admin_permission) or DEFAULT_ADMIN_PERMISSIONS
    reader_permissions = _csv_or_repeated(args.reader_permission) or DEFAULT_READER_PERMISSIONS

    user_store = PgEnterpriseUserStore(dsn=args.dsn, max_size=1)
    role_store = PgEnterpriseRoleStore(dsn=args.dsn, max_size=1)
    grant_store = PgEnterpriseDatasourceGrantStore(dsn=args.dsn, max_size=1)
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

        grant_scope = {
            "allow_catalog": True,
            "allow_sql": True,
            "schemas": schemas,
            "tables": tables,
        }
        admin_grant = await grant_store.put_grant(
            subject_type="role",
            subject_id=args.admin_role,
            datasource_key=args.datasource,
            effect="allow",
            scope=grant_scope,
        )
        reader_grant = None
        if not args.skip_reader_grant:
            reader_grant = await grant_store.put_grant(
                subject_type="role",
                subject_id=args.reader_role,
                datasource_key=args.datasource,
                effect="allow",
                scope=grant_scope,
            )

        return {
            "users": [admin_user, reader_user],
            "roles": [admin_role, reader_role],
            "user_roles": {
                args.admin_user: admin_roles,
                args.reader_user: reader_roles,
            },
            "datasource_grants": [item for item in [admin_grant, reader_grant] if item is not None],
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

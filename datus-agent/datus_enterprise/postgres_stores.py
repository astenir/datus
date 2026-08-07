"""Compatibility imports for the PostgreSQL enterprise persistence adapter.

New code should import public stores from ``datus_enterprise.storage.postgres``.
The legacy module remains stable for deployed configuration class paths and
downstream callers while the adapter is split incrementally.
"""

import asyncio

from datus_enterprise.storage.postgres.stores import (
    _SCHEMA_SQL,
    PgArtifactAclStore,
    PgAuditSink,
    PgEnterpriseAgentStore,
    PgEnterpriseDatasourceGrantStore,
    PgEnterpriseQuotaStore,
    PgEnterpriseRoleStore,
    PgEnterpriseSecretStore,
    PgEnterpriseUserStore,
    PgSessionOwnerStore,
    PgUserDatasourceStore,
    PgUserMcpServerStore,
    PgUserModelCredentialStore,
    _agent_record,
    _close_pool_best_effort,
    _is_transient_pg_connection_error,
    _normalized_agent_metadata,
    _query_summary,
)

__all__ = [
    "_SCHEMA_SQL",
    "_agent_record",
    "_close_pool_best_effort",
    "_is_transient_pg_connection_error",
    "_normalized_agent_metadata",
    "_query_summary",
    "asyncio",
    "PgArtifactAclStore",
    "PgAuditSink",
    "PgEnterpriseAgentStore",
    "PgEnterpriseDatasourceGrantStore",
    "PgEnterpriseQuotaStore",
    "PgEnterpriseRoleStore",
    "PgEnterpriseSecretStore",
    "PgEnterpriseUserStore",
    "PgSessionOwnerStore",
    "PgUserDatasourceStore",
    "PgUserModelCredentialStore",
    "PgUserMcpServerStore",
]

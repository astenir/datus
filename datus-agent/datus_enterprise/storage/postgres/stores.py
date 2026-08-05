"""Compatibility exports for split PostgreSQL enterprise stores.

Prefer importing public classes from the datus_enterprise.storage.postgres
package. Private exports remain available while legacy imports and tests migrate.
"""

import asyncio

from datus_enterprise.storage.common.normalization import _normalized_agent_metadata
from datus_enterprise.storage.postgres.base import (
    _close_pool_best_effort,
    _is_transient_pg_connection_error,
    _query_summary,
)
from datus_enterprise.storage.postgres.governance import (
    PgArtifactAclStore,
    PgAuditSink,
    PgEnterpriseQuotaStore,
    PgEnterpriseSecretStore,
    PgSessionOwnerStore,
)
from datus_enterprise.storage.postgres.identity import PgEnterpriseRoleStore, PgEnterpriseUserStore
from datus_enterprise.storage.postgres.records import _agent_record
from datus_enterprise.storage.postgres.resources import (
    PgEnterpriseAgentStore,
    PgEnterpriseDatasourceGrantStore,
)
from datus_enterprise.storage.postgres.schema import _SCHEMA_SQL
from datus_enterprise.storage.postgres.user_resources import (
    PgUserDatasourceStore,
    PgUserModelCredentialStore,
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
]

"""Compatibility imports for the OceanBase enterprise persistence adapter.

New code should import public stores from datus_enterprise.storage.oceanbase.
The legacy module remains stable for deployed configuration class paths.
"""

from datus_enterprise.storage.oceanbase.stores import (
    _SCHEMA_SQL,
    ObArtifactAclStore,
    ObAuditSink,
    ObEnterpriseAgentStore,
    ObEnterpriseDatasourceGrantStore,
    ObEnterpriseQuotaStore,
    ObEnterpriseRoleStore,
    ObEnterpriseSecretStore,
    ObEnterpriseUserStore,
    ObSessionOwnerStore,
    ObUserDatasourceStore,
    ObUserModelCredentialStore,
)

__all__ = [
    "_SCHEMA_SQL",
    "ObArtifactAclStore",
    "ObAuditSink",
    "ObEnterpriseAgentStore",
    "ObEnterpriseDatasourceGrantStore",
    "ObEnterpriseQuotaStore",
    "ObEnterpriseRoleStore",
    "ObEnterpriseSecretStore",
    "ObEnterpriseUserStore",
    "ObSessionOwnerStore",
    "ObUserDatasourceStore",
    "ObUserModelCredentialStore",
]

import sys
import types

import pytest

from datus.api.enterprise.defaults import (
    InMemoryEnterpriseDatasourceGrantStore,
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import load_enterprise_extensions
from datus.utils.exceptions import DatusException


class _Authz:
    async def check(self, ctx, action, resource):
        return None

    async def allowed_datasources(self, ctx):
        return {}


class _Projector:
    async def project(self, request):
        return None


class _Audit:
    async def write(self, event):
        return None


class _UserStore:
    async def list_users(self, *, enabled=None):
        return []

    async def get_user(self, user_id):
        return None

    async def upsert_user(self, *, user_id, display_name=None, email=None, enabled=True):
        return {}

    async def set_user_enabled(self, user_id, enabled):
        return None


class _RoleStore:
    async def list_roles(self):
        return []

    async def get_role(self, role_id):
        return None

    async def upsert_role(
        self,
        *,
        role_id,
        name,
        description=None,
        permissions=None,
        built_in=False,
    ):
        return {}

    async def set_role_permissions(self, role_id, permissions):
        return None

    async def list_user_roles(self, user_id):
        return []

    async def set_user_roles(self, user_id, role_ids):
        return []

    async def list_role_users(self, role_id):
        return []

    async def delete_role(self, role_id):
        return False


class _DatasourceGrantStore:
    async def list_grants(self, *, subject_type=None, subject_id=None, datasource_key=None):
        return []

    async def get_grant(self, *, subject_type, subject_id, datasource_key):
        return None

    async def put_grant(self, *, subject_type, subject_id, datasource_key, effect, scope=None):
        return {}

    async def delete_grant(self, *, subject_type, subject_id, datasource_key):
        return False


class _ArtifactAclStore:
    async def get_acl(self, *, artifact_type, slug):
        return {}

    async def put_acl(self, *, artifact_type, slug, acl):
        return acl


class _LegacyOwnerStore:
    async def set_owner(self, project_id, session_id, user_id):
        return None

    async def get_owner(self, project_id, session_id):
        return None

    async def delete_owner(self, project_id, session_id):
        return None

    async def list_session_ids(self, project_id, user_id):
        return []


class _OwnerStore(_LegacyOwnerStore):
    async def list_sessions(self, project_id, user_id=None):
        return []


@pytest.fixture
def fake_module():
    mod_name = "_datus_test_fake_enterprise_mod"
    mod = types.ModuleType(mod_name)
    mod.Authz = _Authz
    mod.Projector = _Projector
    mod.Audit = _Audit
    mod.UserStore = _UserStore
    mod.RoleStore = _RoleStore
    mod.DatasourceGrantStore = _DatasourceGrantStore
    mod.ArtifactAclStore = _ArtifactAclStore
    mod.LegacyOwnerStore = _LegacyOwnerStore
    mod.OwnerStore = _OwnerStore
    sys.modules[mod_name] = mod
    yield mod_name
    sys.modules.pop(mod_name, None)


def test_disabled_enterprise_loads_local_defaults():
    extensions = load_enterprise_extensions(None)

    assert extensions.enabled is False
    assert extensions.authorization_provider is not None
    assert extensions.config_projector is not None
    assert isinstance(extensions.user_store, InMemoryEnterpriseUserStore)
    assert isinstance(extensions.role_store, InMemoryEnterpriseRoleStore)
    assert isinstance(extensions.datasource_grant_store, InMemoryEnterpriseDatasourceGrantStore)
    assert extensions.session_owner_store is not None
    assert extensions.audit_sink is not None
    assert extensions.artifact_acl_store is None


def test_enabled_enterprise_requires_core_providers():
    with pytest.raises(DatusException, match="authorization_provider"):
        load_enterprise_extensions({"enabled": True})


def test_enabled_enterprise_uses_passthrough_projector_when_projection_not_configured(fake_module):
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": f"{fake_module}.Authz"},
            "audit_sink": {"class": f"{fake_module}.Audit"},
        }
    )

    assert extensions.enabled is True
    assert isinstance(extensions.config_projector, PassthroughConfigProjector)
    assert isinstance(extensions.user_store, InMemoryEnterpriseUserStore)
    assert isinstance(extensions.role_store, InMemoryEnterpriseRoleStore)
    assert isinstance(extensions.datasource_grant_store, InMemoryEnterpriseDatasourceGrantStore)
    assert extensions.artifact_acl_store is None


def test_enabled_enterprise_loads_configured_core_providers(fake_module):
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": f"{fake_module}.Authz"},
            "config_projector": {"class": f"{fake_module}.Projector"},
            "user_store": {"class": f"{fake_module}.UserStore"},
            "role_store": {"class": f"{fake_module}.RoleStore"},
            "datasource_grant_store": {"class": f"{fake_module}.DatasourceGrantStore"},
            "artifact_acl_store": {"class": f"{fake_module}.ArtifactAclStore"},
            "audit_sink": {"class": f"{fake_module}.Audit"},
            "session_owner_store": {"class": f"{fake_module}.OwnerStore"},
        }
    )

    assert extensions.enabled is True
    assert isinstance(extensions.authorization_provider, _Authz)
    assert isinstance(extensions.config_projector, _Projector)
    assert isinstance(extensions.user_store, _UserStore)
    assert isinstance(extensions.role_store, _RoleStore)
    assert isinstance(extensions.datasource_grant_store, _DatasourceGrantStore)
    assert isinstance(extensions.audit_sink, _Audit)
    assert isinstance(extensions.artifact_acl_store, _ArtifactAclStore)
    assert isinstance(extensions.session_owner_store, _OwnerStore)


def test_enabled_enterprise_rejects_owner_store_without_admin_listing(fake_module):
    with pytest.raises(DatusException, match="session_owner_store"):
        load_enterprise_extensions(
            {
                "enabled": True,
                "authorization_provider": {"class": f"{fake_module}.Authz"},
                "audit_sink": {"class": f"{fake_module}.Audit"},
                "session_owner_store": {"class": f"{fake_module}.LegacyOwnerStore"},
            }
        )

import sys
import types

import pytest

from datus.api.enterprise.defaults import PassthroughConfigProjector
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


class _ArtifactAclStore:
    async def get_acl(self, *, artifact_type, slug):
        return {}

    async def put_acl(self, *, artifact_type, slug, acl):
        return acl


@pytest.fixture
def fake_module():
    mod_name = "_datus_test_fake_enterprise_mod"
    mod = types.ModuleType(mod_name)
    mod.Authz = _Authz
    mod.Projector = _Projector
    mod.Audit = _Audit
    mod.ArtifactAclStore = _ArtifactAclStore
    sys.modules[mod_name] = mod
    yield mod_name
    sys.modules.pop(mod_name, None)


def test_disabled_enterprise_loads_local_defaults():
    extensions = load_enterprise_extensions(None)

    assert extensions.enabled is False
    assert extensions.authorization_provider is not None
    assert extensions.config_projector is not None
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
    assert extensions.artifact_acl_store is None


def test_enabled_enterprise_loads_configured_core_providers(fake_module):
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": f"{fake_module}.Authz"},
            "config_projector": {"class": f"{fake_module}.Projector"},
            "artifact_acl_store": {"class": f"{fake_module}.ArtifactAclStore"},
            "audit_sink": {"class": f"{fake_module}.Audit"},
        }
    )

    assert extensions.enabled is True
    assert isinstance(extensions.authorization_provider, _Authz)
    assert isinstance(extensions.config_projector, _Projector)
    assert isinstance(extensions.audit_sink, _Audit)
    assert isinstance(extensions.artifact_acl_store, _ArtifactAclStore)

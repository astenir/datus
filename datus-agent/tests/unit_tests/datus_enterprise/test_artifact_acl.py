import pytest
from fastapi import HTTPException

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.artifact_acl import filter_visible_artifacts, require_artifact_access


class MemoryArtifactAclStore:
    def __init__(self, initial=None):
        self.acls = dict(initial or {})

    async def get_acl(self, *, artifact_type: str, slug: str):
        key = (artifact_type, slug)
        if key not in self.acls:
            raise KeyError(key)
        return dict(self.acls[key])

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict):
        self.acls[(artifact_type, slug)] = dict(acl)
        return dict(acl)


def _manifest(slug: str, kind: str = "report") -> ArtifactManifest:
    return ArtifactManifest(
        slug=slug, name=slug, description="Test artifact", kind=kind, created_at="2026-01-01T00:00:00Z"
    )


@pytest.mark.asyncio
async def test_filter_visible_artifacts_allows_all_without_acl():
    manifests = [_manifest("a"), _manifest("b")]

    result = await filter_visible_artifacts(AppContext(), artifact_type="report", manifests=manifests)

    assert [item.slug for item in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_filter_visible_artifacts_uses_principal_acl():
    manifests = [_manifest("a"), _manifest("b")]
    ctx = AppContext(principal={"artifact_acl": {"report": ["b"]}})

    result = await filter_visible_artifacts(ctx, artifact_type="report", manifests=manifests)

    assert [item.slug for item in result] == ["b"]


@pytest.mark.asyncio
async def test_require_artifact_access_returns_404_for_acl_miss():
    ctx = AppContext(principal={"artifact_acl": {"dashboard": ["visible"]}})

    with pytest.raises(HTTPException) as exc:
        await require_artifact_access(ctx, artifact_type="dashboard", slug="hidden", action="view")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_artifact_access_uses_configured_acl_store(monkeypatch):
    store = MemoryArtifactAclStore(
        {
            ("dashboard", "private_ops"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "datasources": [],
            }
        }
    )
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            artifact_acl_store=store,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await require_artifact_access(
            AppContext(user_id="viewer-1", permissions={"module.dashboard.query"}),
            artifact_type="dashboard",
            slug="private_ops",
            action="query",
        )

    assert exc.value.status_code == 404

    await require_artifact_access(
        AppContext(user_id="owner-1", permissions={"module.dashboard.query"}),
        artifact_type="dashboard",
        slug="private_ops",
        action="query",
    )

    await require_artifact_access(
        AppContext(user_id="admin-1", permissions={"module.dashboard.query", "module.admin.*"}),
        artifact_type="dashboard",
        slug="private_ops",
        action="query",
    )


@pytest.mark.asyncio
async def test_require_artifact_access_does_not_trust_principal_admin_when_permissions_present(monkeypatch):
    store = MemoryArtifactAclStore(
        {
            ("report", "private_sales"): {
                "owner_user_id": "owner-1",
                "visibility": "private",
                "allowed_roles": [],
                "datasources": [],
            }
        }
    )
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            artifact_acl_store=store,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await require_artifact_access(
            AppContext(
                user_id="viewer-1",
                permissions={"module.report.view"},
                principal={"permissions": ["module.admin.artifacts"]},
            ),
            artifact_type="report",
            slug="private_sales",
            action="view",
        )

    assert exc.value.status_code == 404

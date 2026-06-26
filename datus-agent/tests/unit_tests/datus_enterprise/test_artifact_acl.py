import pytest
from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.artifact_acl import filter_visible_artifacts, require_artifact_access


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

import pytest

from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import InMemorySessionOwnerStore, LocalAuthorizationProvider, SqliteSessionOwnerStore
from datus.api.enterprise.models import ResourceRef


@pytest.mark.asyncio
async def test_local_authorization_uses_app_context_permissions_first():
    provider = LocalAuthorizationProvider()
    ctx = AppContext(permissions={"module.dashboard.*"}, principal={"permissions": ["module.report.*"]})

    allowed = await provider.check(ctx, "module.dashboard.view", ResourceRef(type="dashboard"))
    denied = await provider.check(ctx, "module.report.view", ResourceRef(type="report"))

    assert allowed.allowed is True
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_local_authorization_keeps_principal_permissions_compatibility():
    provider = LocalAuthorizationProvider()
    ctx = AppContext(principal={"permissions": ["module.report.*"]})

    decision = await provider.check(ctx, "module.report.view", ResourceRef(type="report"))

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_in_memory_session_owner_store_supports_delete_and_user_listing():
    store = InMemorySessionOwnerStore()

    await store.set_owner("project", "s1", "alice")
    await store.set_owner("project", "s2", "alice")
    await store.set_owner("project", "s3", "bob")
    await store.delete_owner("project", "s1")

    assert await store.get_owner("project", "s1") is None
    assert await store.get_owner("project", "s2") == "alice"
    assert await store.list_session_ids("project", "alice") == ["s2"]
    assert await store.list_sessions("project") == [
        {
            "project_id": "project",
            "session_id": "s2",
            "user_id": "alice",
            "created_at": None,
            "updated_at": None,
        },
        {
            "project_id": "project",
            "session_id": "s3",
            "user_id": "bob",
            "created_at": None,
            "updated_at": None,
        },
    ]
    assert await store.list_sessions("project", user_id="alice") == [
        {
            "project_id": "project",
            "session_id": "s2",
            "user_id": "alice",
            "created_at": None,
            "updated_at": None,
        }
    ]


@pytest.mark.asyncio
async def test_sqlite_session_owner_store_persists_session_owners(tmp_path):
    db_path = tmp_path / "session_owners.db"
    store = SqliteSessionOwnerStore(str(db_path))

    await store.set_owner("project", "s1", "alice@example.com")
    await store.set_owner("project", "s2", "alice@example.com")
    await store.set_owner("project", "s1", "bob@example.com")

    reopened = SqliteSessionOwnerStore(str(db_path))
    assert await reopened.get_owner("project", "s1") == "bob@example.com"
    assert await reopened.get_owner("project", "s2") == "alice@example.com"
    assert await reopened.list_session_ids("project", "alice@example.com") == ["s2"]
    sessions = await reopened.list_sessions("project")
    assert [
        {"project_id": item["project_id"], "session_id": item["session_id"], "user_id": item["user_id"]}
        for item in sessions
    ] == [
        {"project_id": "project", "session_id": "s1", "user_id": "bob@example.com"},
        {"project_id": "project", "session_id": "s2", "user_id": "alice@example.com"},
    ]
    assert sessions[0]["created_at"]
    assert sessions[0]["updated_at"]

    await reopened.delete_owner("project", "s2")
    assert await reopened.get_owner("project", "s2") is None

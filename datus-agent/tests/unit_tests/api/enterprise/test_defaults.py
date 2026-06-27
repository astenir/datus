import pytest

from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    SqliteEnterpriseRoleStore,
    SqliteEnterpriseUserStore,
    SqliteSessionOwnerStore,
)
from datus.api.enterprise.models import ResourceRef
from datus.utils.exceptions import DatusException


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
async def test_in_memory_enterprise_user_store_supports_upsert_and_enabled_filter():
    store = InMemoryEnterpriseUserStore()

    alice = await store.upsert_user(user_id="alice", display_name="Alice", email="alice@example.com")
    await store.upsert_user(user_id="bob", display_name="Bob", enabled=False)

    assert alice["enabled"] is True
    assert await store.get_user("alice") == alice
    assert [user["user_id"] for user in await store.list_users()] == ["alice", "bob"]
    assert [user["user_id"] for user in await store.list_users(enabled=True)] == ["alice"]
    assert [user["user_id"] for user in await store.list_users(enabled=False)] == ["bob"]

    disabled = await store.set_user_enabled("alice", False)
    assert disabled["enabled"] is False
    assert await store.set_user_enabled("missing", False) is None


@pytest.mark.asyncio
async def test_in_memory_enterprise_role_store_supports_permissions_and_delete():
    store = InMemoryEnterpriseRoleStore()

    analyst = await store.upsert_role(
        role_id="analyst",
        name="Analyst",
        description="Can analyze data",
        permissions=["module.chat", "module.sql_executor", "module.chat"],
    )

    assert analyst["permissions"] == ["module.chat", "module.sql_executor"]
    assert await store.get_role("analyst") == analyst
    assert [role["role_id"] for role in await store.list_roles()] == ["analyst"]

    updated = await store.set_role_permissions("analyst", ["module.dashboard.query"])
    assert updated["permissions"] == ["module.dashboard.query"]
    assert await store.set_role_permissions("missing", ["module.chat"]) is None

    assert await store.delete_role("analyst") is True
    assert await store.delete_role("analyst") is False


@pytest.mark.asyncio
async def test_in_memory_enterprise_role_store_supports_user_role_bindings():
    store = InMemoryEnterpriseRoleStore()
    await store.upsert_role(role_id="analyst", name="Analyst")
    await store.upsert_role(role_id="viewer", name="Viewer")

    assigned = await store.set_user_roles("alice", ["viewer", "analyst", "viewer"])

    assert assigned == ["analyst", "viewer"]
    assert await store.list_user_roles("alice") == ["analyst", "viewer"]
    assert await store.list_role_users("viewer") == ["alice"]
    assert await store.delete_role("viewer") is False

    assert await store.set_user_roles("alice", []) == []
    assert await store.list_user_roles("alice") == []
    assert await store.delete_role("viewer") is True


@pytest.mark.asyncio
async def test_in_memory_enterprise_role_store_rejects_missing_user_role_binding():
    store = InMemoryEnterpriseRoleStore()
    await store.upsert_role(role_id="analyst", name="Analyst")

    with pytest.raises(DatusException, match="Role not found: missing"):
        await store.set_user_roles("alice", ["analyst", "missing"])

    assert await store.list_user_roles("alice") == []


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


@pytest.mark.asyncio
async def test_sqlite_enterprise_user_store_persists_users(tmp_path):
    db_path = tmp_path / "enterprise_users.db"
    store = SqliteEnterpriseUserStore(str(db_path))

    await store.upsert_user(user_id="alice", display_name="Alice", email="alice@example.com")
    await store.upsert_user(user_id="bob", display_name="Bob", enabled=False)
    await store.upsert_user(user_id="alice", display_name="Alice A", enabled=False)

    reopened = SqliteEnterpriseUserStore(str(db_path))
    alice = await reopened.get_user("alice")
    assert alice["display_name"] == "Alice A"
    assert alice["email"] is None
    assert alice["enabled"] is False
    assert alice["created_at"]
    assert alice["updated_at"]
    assert [user["user_id"] for user in await reopened.list_users(enabled=False)] == ["alice", "bob"]

    enabled = await reopened.set_user_enabled("alice", True)
    assert enabled["enabled"] is True
    assert await reopened.set_user_enabled("missing", False) is None


@pytest.mark.asyncio
async def test_sqlite_enterprise_role_store_persists_roles_and_permissions(tmp_path):
    db_path = tmp_path / "enterprise_roles.db"
    store = SqliteEnterpriseRoleStore(str(db_path))

    await store.upsert_role(
        role_id="analyst",
        name="Analyst",
        description="Can analyze data",
        permissions=["module.sql_executor", "module.chat"],
    )
    await store.upsert_role(role_id="viewer", name="Viewer", permissions=["module.report.view"], built_in=True)
    await store.set_role_permissions("analyst", ["module.dashboard.query", "module.report.query"])

    reopened = SqliteEnterpriseRoleStore(str(db_path))
    analyst = await reopened.get_role("analyst")
    assert analyst["name"] == "Analyst"
    assert analyst["description"] == "Can analyze data"
    assert analyst["permissions"] == ["module.dashboard.query", "module.report.query"]
    assert analyst["built_in"] is False
    assert analyst["created_at"]
    assert analyst["updated_at"]
    assert [role["role_id"] for role in await reopened.list_roles()] == ["analyst", "viewer"]
    assert (await reopened.get_role("viewer"))["built_in"] is True

    assert await reopened.delete_role("analyst") is True
    assert await reopened.get_role("analyst") is None
    assert await reopened.delete_role("missing") is False


@pytest.mark.asyncio
async def test_sqlite_enterprise_role_store_persists_user_role_bindings(tmp_path):
    db_path = tmp_path / "enterprise_roles.db"
    store = SqliteEnterpriseRoleStore(str(db_path))
    await store.upsert_role(role_id="analyst", name="Analyst")
    await store.upsert_role(role_id="viewer", name="Viewer")

    await store.set_user_roles("alice", ["viewer", "analyst", "viewer"])

    reopened = SqliteEnterpriseRoleStore(str(db_path))
    assert await reopened.list_user_roles("alice") == ["analyst", "viewer"]
    assert await reopened.list_role_users("analyst") == ["alice"]
    assert await reopened.delete_role("analyst") is False

    assert await reopened.set_user_roles("alice", ["viewer"]) == ["viewer"]
    assert await reopened.list_user_roles("alice") == ["viewer"]
    assert await reopened.list_role_users("analyst") == []
    assert await reopened.delete_role("analyst") is True


@pytest.mark.asyncio
async def test_sqlite_enterprise_role_store_rejects_missing_user_role_binding(tmp_path):
    db_path = tmp_path / "enterprise_roles.db"
    store = SqliteEnterpriseRoleStore(str(db_path))
    await store.upsert_role(role_id="analyst", name="Analyst")

    with pytest.raises(DatusException, match="Role not found: missing"):
        await store.set_user_roles("alice", ["analyst", "missing"])

    reopened = SqliteEnterpriseRoleStore(str(db_path))
    assert await reopened.list_user_roles("alice") == []

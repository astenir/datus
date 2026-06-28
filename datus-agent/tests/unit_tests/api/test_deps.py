"""Tests for datus.api.deps — dependency injection module."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import get_datus_service, get_request_app_context, init_deps
from datus.api.services.datus_service_cache import DatusServiceCache
from datus.utils.exceptions import DatusException, ErrorCode


@pytest.fixture(autouse=True)
def _reset_deps():
    """Reset module-level singletons between tests."""
    deps._auth_provider = None
    deps._service_cache = None
    deps._enterprise_extensions = None
    deps._datasource = "default"
    deps._default_source = None
    deps._default_interactive = True
    yield
    deps._auth_provider = None
    deps._service_cache = None
    deps._enterprise_extensions = None
    deps._datasource = "default"
    deps._default_source = None
    deps._default_interactive = True


class TestInitDeps:
    """Tests for init_deps — singleton initialization."""

    def test_sets_auth_provider(self):
        """init_deps stores the auth provider."""
        mock_auth = MagicMock()
        mock_auth.on_evict = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)

        init_deps(mock_auth, mock_cache, datasource="test_ns")

        assert deps._auth_provider is mock_auth
        assert deps._service_cache is mock_cache
        assert deps._datasource == "test_ns"

    def test_default_datasource(self):
        """Default datasource is 'default'."""
        mock_auth = MagicMock()
        mock_auth.on_evict = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)

        init_deps(mock_auth, mock_cache)
        assert deps._datasource == "default"

    def test_default_source_and_interactive_defaults(self):
        """Without explicit args, default_source is None and default_interactive is True."""
        mock_auth = MagicMock()
        mock_auth.on_evict = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)

        init_deps(mock_auth, mock_cache)
        assert deps._default_source is None
        assert deps._default_interactive is True

    def test_default_source_and_interactive_stored(self):
        """init_deps stores explicit default_source and default_interactive."""
        mock_auth = MagicMock()
        mock_auth.on_evict = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)

        init_deps(
            mock_auth,
            mock_cache,
            datasource="ns",
            default_source="vscode",
            default_interactive=False,
        )
        assert deps._default_source == "vscode"
        assert deps._default_interactive is False

    def test_wires_eviction_callback(self):
        """init_deps wires auth_provider.on_evict through mode-aware eviction."""
        mock_auth = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.evict = AsyncMock()

        init_deps(mock_auth, mock_cache)
        callback = mock_auth.on_evict.call_args.args[0]
        asyncio.run(callback("proj/a"))
        mock_cache.evict.assert_awaited_once_with(deps.service_cache_key("proj/a", enterprise_enabled=False))

    def test_wires_enterprise_eviction_callback_with_enterprise_cache_key(self):
        """Enterprise mode evicts enterprise-prefixed service cache entries."""
        from datus.api.enterprise.defaults import (
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        mock_cache = MagicMock(spec=DatusServiceCache)
        extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        )

        init_deps(mock_auth, mock_cache, enterprise_extensions=extensions)

        callback = mock_auth.on_evict.call_args.args[0]
        asyncio.run(callback("proj/a"))
        mock_cache.evict.assert_awaited_once_with(deps.service_cache_key("proj/a", enterprise_enabled=True))


@pytest.mark.asyncio
class TestGetRequestAppContext:
    """Tests for request context authentication and enterprise metadata refresh."""

    async def test_enterprise_context_is_authenticated_refreshed_and_cached_once(self):
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        role_store = InMemoryEnterpriseRoleStore()
        await role_store.upsert_role(role_id="analyst", name="Analyst", permissions=["module.chat"])
        await role_store.set_user_roles("alice", ["analyst"])
        list_user_roles = role_store.list_user_roles
        role_store.list_user_roles = AsyncMock(side_effect=list_user_roles)

        grant_store = InMemoryEnterpriseDatasourceGrantStore()
        await grant_store.put_grant(
            subject_type="role",
            subject_id="analyst",
            datasource_key="finance",
            effect="allow",
            scope={"allow_catalog": True, "tables": ["public.accounts"]},
        )
        list_grants = grant_store.list_grants
        grant_store.list_grants = AsyncMock(side_effect=list_grants)

        ctx = AppContext(user_id="alice", project_id="proj-1")
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=ctx)
        deps._auth_provider = mock_auth
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
            datasource_grant_store=grant_store,
        )
        request = SimpleNamespace(state=SimpleNamespace())

        first = await get_request_app_context(request)
        second = await get_request_app_context(request)

        assert first is ctx
        assert second is ctx
        assert request.state.app_context_enterprise_ready is True
        assert ctx.roles == ["analyst"]
        assert ctx.permissions == {"module.chat"}
        assert ctx.datasource_grants["finance"]["tables"] == ["public.accounts"]
        mock_auth.authenticate.assert_awaited_once_with(request)
        role_store.list_user_roles.assert_awaited_once_with("alice")
        assert grant_store.list_grants.await_count == 2
        grant_store.list_grants.assert_any_await(subject_type="role", subject_id="analyst")
        grant_store.list_grants.assert_any_await(subject_type="user", subject_id="alice")

    async def test_enterprise_context_refreshes_cached_context_before_reuse(self):
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        role_store = InMemoryEnterpriseRoleStore()
        await role_store.upsert_role(role_id="viewer", name="Viewer", permissions=["module.report.view"])
        await role_store.set_user_roles("alice", ["viewer"])
        cached_ctx = AppContext(
            user_id="alice",
            project_id="proj-1",
            roles=["stale_admin"],
            permissions={"module.admin.users"},
            datasource_grants={"legacy": {"effect": "allow"}},
        )
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock()
        deps._auth_provider = mock_auth
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
            datasource_grant_store=InMemoryEnterpriseDatasourceGrantStore(),
        )
        request = SimpleNamespace(state=SimpleNamespace(app_context=cached_ctx))

        result = await get_request_app_context(request)

        assert result is cached_ctx
        assert request.state.app_context_enterprise_ready is True
        assert cached_ctx.roles == ["viewer"]
        assert cached_ctx.permissions == {"module.report.view"}
        assert cached_ctx.datasource_grants == {}
        mock_auth.authenticate.assert_not_awaited()

    async def test_enterprise_context_missing_user_fails_before_service_cache(self):
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=AppContext(project_id="proj-1"))
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock()
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_request_app_context(SimpleNamespace(state=SimpleNamespace()))

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "AUTH_REQUIRED"
        mock_cache.get_or_create.assert_not_called()


@pytest.mark.asyncio
class TestGetDatusService:
    """Tests for get_datus_service — FastAPI dependency."""

    async def test_raises_when_auth_not_initialized(self):
        """RuntimeError when auth_provider is None."""
        request = MagicMock()
        with pytest.raises(RuntimeError, match="Auth provider not initialized"):
            await get_datus_service(request)

    async def test_raises_when_cache_not_initialized(self):
        """RuntimeError when service_cache is None but auth is set."""
        deps._auth_provider = MagicMock()
        deps._auth_provider.authenticate = AsyncMock()
        request = MagicMock()
        request.state = MagicMock()
        with pytest.raises(RuntimeError, match="Service cache not initialized"):
            await get_datus_service(request)

    async def test_authenticates_and_returns_service(self):
        """Full flow: authenticate → factory → cache.get_or_create."""
        from unittest.mock import patch

        mock_auth = MagicMock()
        ctx = AppContext(user_id="user-1", project_id="proj-1", config=MagicMock())
        mock_auth.authenticate = AsyncMock(return_value=ctx)

        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_svc = MagicMock()
        mock_cache.get_or_create = AsyncMock(return_value=mock_svc)

        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache

        request = MagicMock()
        request.state = MagicMock()
        with patch(
            "datus.api.deps.DatusService.compute_fingerprint",
            return_value="fp-xyz",
        ) as mock_fp:
            result = await get_datus_service(request)

        assert result is mock_svc
        mock_auth.authenticate.assert_awaited_once_with(request)
        mock_cache.get_or_create.assert_awaited_once()
        mock_fp.assert_called_once_with(ctx.config)
        call_args = mock_cache.get_or_create.call_args
        assert call_args[0][0] == "proj-1"
        assert call_args.kwargs["expected_fingerprint"] == "fp-xyz"

    async def test_enterprise_cache_key_is_prefixed_but_service_project_id_is_plain(self):
        """Enterprise cache isolation does not leak the cache prefix into DatusService.project_id."""
        from unittest.mock import patch

        from datus.api.enterprise.defaults import (
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        ctx = AppContext(
            user_id="user-1",
            project_id="proj-1",
            config=MagicMock(),
            roles=["analyst"],
            permissions={"module.chat"},
        )
        mock_auth.authenticate = AsyncMock(return_value=ctx)

        mock_cache = MagicMock(spec=DatusServiceCache)
        captured = {}

        async def fake_get_or_create(key, factory, expected_fingerprint=None):
            captured["key"] = key
            captured["svc"] = await factory()
            return captured["svc"]

        mock_cache.get_or_create = AsyncMock(side_effect=fake_get_or_create)
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        )

        request = MagicMock()
        request.state = MagicMock()

        with (
            patch("datus.api.deps.DatusService.compute_fingerprint", return_value="fp"),
            patch("datus.api.deps.DatusService") as mock_svc_cls,
        ):
            mock_svc_cls.compute_fingerprint = MagicMock(return_value="fp")
            mock_svc_cls.return_value = MagicMock()
            await get_datus_service(request)

        assert captured["key"] == "enterprise:proj-1"
        assert mock_svc_cls.call_args.kwargs["project_id"] == "proj-1"

    async def test_enterprise_context_missing_user_fails_closed(self):
        """Enterprise mode rejects unauthenticated request context before service lookup."""
        from datus.api.enterprise.defaults import (
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=AppContext(roles=["analyst"], permissions={"module.chat"}))
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock()
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        )

        request = MagicMock()
        request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_datus_service(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "AUTH_REQUIRED"
        mock_cache.get_or_create.assert_not_called()

    async def test_enterprise_identity_only_context_reaches_service_cache(self):
        """Enterprise auth providers may return identity-only contexts and leave RBAC to authz dependencies."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        ctx = AppContext(user_id="u1", project_id="proj-1", config=MagicMock())
        mock_auth.authenticate = AsyncMock(return_value=ctx)
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_svc = MagicMock()
        mock_cache.get_or_create = AsyncMock(return_value=mock_svc)
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=InMemoryEnterpriseRoleStore(),
            datasource_grant_store=InMemoryEnterpriseDatasourceGrantStore(),
        )

        request = MagicMock()
        request.state = MagicMock()
        result = await get_datus_service(request)

        assert result is mock_svc
        mock_cache.get_or_create.assert_awaited_once()

    async def test_enterprise_context_refreshes_roles_permissions_and_datasource_grants(self):
        """Enterprise metadata stores are merged into the request AppContext before route dependencies run."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        role_store = InMemoryEnterpriseRoleStore()
        grant_store = InMemoryEnterpriseDatasourceGrantStore()
        await role_store.upsert_role(role_id="analyst", name="Analyst", permissions=["module.chat"])
        await role_store.set_user_roles("alice", ["analyst"])
        await grant_store.put_grant(
            subject_type="role",
            subject_id="analyst",
            datasource_key="finance",
            effect="allow",
            scope={"allow_sql": True, "tables": ["role_table", "user_table"]},
        )
        await grant_store.put_grant(
            subject_type="user",
            subject_id="alice",
            datasource_key="finance",
            effect="allow",
            scope={"allow_sql": True, "tables": ["user_table"]},
        )
        await grant_store.put_grant(
            subject_type="user",
            subject_id="alice",
            datasource_key="hr",
            effect="deny",
            scope={},
        )

        ctx = AppContext(user_id="alice", project_id="proj-1", config=MagicMock(), permissions={"module.report.view"})
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=ctx)
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock(return_value=MagicMock())
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
            datasource_grant_store=grant_store,
        )

        request = MagicMock()
        request.state = MagicMock()
        await get_datus_service(request)

        assert ctx.roles == ["analyst"]
        assert ctx.permissions == {"module.chat"}
        assert ctx.datasource_grants == {
            "finance": {
                "allow_catalog": True,
                "allow_sql": True,
                "tables": ["user_table"],
                "effect": "allow",
            },
            "hr": {"effect": "deny"},
        }
        assert ctx.principal["permissions"] == ["module.chat"]
        assert ctx.principal["datasource_grants"] == ctx.datasource_grants

    async def test_enterprise_context_combines_same_datasource_role_grants(self):
        """Multiple roles granting the same datasource must not drop compatible scope entries."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        role_store = InMemoryEnterpriseRoleStore()
        grant_store = InMemoryEnterpriseDatasourceGrantStore()
        await role_store.upsert_role(role_id="finance_reader", name="Finance Reader", permissions=["module.chat"])
        await role_store.upsert_role(
            role_id="public_reader", name="Public Reader", permissions=["module.dashboard.query"]
        )
        await role_store.set_user_roles("alice", ["finance_reader", "public_reader"])
        await grant_store.put_grant(
            subject_type="role",
            subject_id="finance_reader",
            datasource_key="finance",
            effect="allow",
            scope={"tables": ["finance_*"]},
        )
        await grant_store.put_grant(
            subject_type="role",
            subject_id="public_reader",
            datasource_key="finance",
            effect="allow",
            scope={"schemas": ["public"]},
        )

        ctx = AppContext(user_id="alice", project_id="proj-1", config=MagicMock())
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=ctx)
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock(return_value=MagicMock())
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
            datasource_grant_store=grant_store,
        )

        request = MagicMock()
        request.state = MagicMock()
        await get_datus_service(request)

        assert ctx.permissions == {"module.chat", "module.dashboard.query"}
        assert ctx.datasource_grants["finance"] == {
            "allow_catalog": True,
            "allow_sql": True,
            "schemas": ["public"],
            "tables": ["finance_*"],
            "effect": "allow",
        }

    async def test_enterprise_context_replaces_stale_authz_fields_from_auth_context(self):
        """Metadata refresh is authoritative for reserved enterprise authorization fields."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        role_store = InMemoryEnterpriseRoleStore()
        grant_store = InMemoryEnterpriseDatasourceGrantStore()
        await role_store.upsert_role(role_id="analyst", name="Analyst", permissions=["module.chat"])
        await role_store.set_user_roles("alice", ["analyst"])

        ctx = AppContext(
            user_id="alice",
            project_id="proj-1",
            config=MagicMock(),
            roles=["stale_admin"],
            permissions={"module.admin.users"},
            datasource_grants={"legacy": {"effect": "allow"}},
            principal={
                "department": "finance",
                "roles": ["stale_admin"],
                "permissions": ["module.admin.users"],
                "datasource_grants": {"legacy": {"effect": "allow"}},
            },
        )
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=ctx)
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock(return_value=MagicMock())
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
            datasource_grant_store=grant_store,
        )

        request = MagicMock()
        request.state = MagicMock()
        await get_datus_service(request)

        assert ctx.roles == ["analyst"]
        assert ctx.permissions == {"module.chat"}
        assert ctx.datasource_grants == {}
        assert ctx.principal == {
            "department": "finance",
            "roles": ["analyst"],
            "permissions": ["module.chat"],
            "datasource_grants": {},
        }

    async def test_enterprise_context_fails_closed_when_bound_role_is_missing(self):
        """A stale user-role binding must not silently drop permissions in enterprise mode."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseDatasourceGrantStore,
            InMemoryEnterpriseRoleStore,
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        class StaleRoleStore(InMemoryEnterpriseRoleStore):
            async def list_user_roles(self, user_id):
                return ["missing_role"]

        class CollectingAuditSink:
            def __init__(self):
                self.events = []

            async def write(self, event):
                self.events.append(event)

        audit_sink = CollectingAuditSink()
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=AppContext(user_id="alice", project_id="proj-1"))
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock()
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            user_store=InMemoryEnterpriseUserStore(),
            role_store=StaleRoleStore(),
            datasource_grant_store=InMemoryEnterpriseDatasourceGrantStore(),
        )

        request = MagicMock()
        request.state = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_datus_service(request)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "ROLE_CONTEXT_UNAVAILABLE"
        assert audit_sink.events[-1].action == "auth.enterprise_context"
        assert audit_sink.events[-1].reason == "role metadata missing"
        mock_cache.get_or_create.assert_not_called()

    async def test_enterprise_disabled_user_fails_closed(self):
        """Enterprise mode rejects new requests for users disabled in the user store."""
        from datus.api.enterprise.defaults import (
            InMemoryEnterpriseUserStore,
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        class CollectingAuditSink:
            def __init__(self):
                self.events = []

            async def write(self, event):
                self.events.append(event)

        user_store = InMemoryEnterpriseUserStore()
        await user_store.upsert_user(user_id="alice", enabled=False)
        audit_sink = CollectingAuditSink()
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(return_value=AppContext(user_id="alice", project_id="proj-1"))
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock()
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
            user_store=user_store,
        )

        request = MagicMock()
        request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_datus_service(request)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "USER_DISABLED"
        mock_cache.get_or_create.assert_not_called()
        assert audit_sink.events[-1].action == "auth.enterprise_user_status"
        assert audit_sink.events[-1].decision == "deny"

    async def test_enterprise_project_ids_do_not_share_sanitized_cache_key(self):
        """Unsafe project ids keep distinct cache entries and preserve canonical service project ids."""
        from unittest.mock import patch

        from datus.api.enterprise.defaults import (
            InMemorySessionOwnerStore,
            LocalAuthorizationProvider,
            NoopAuditSink,
            PassthroughConfigProjector,
        )
        from datus.api.enterprise.loader import EnterpriseExtensions

        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(
            side_effect=[
                AppContext(user_id="u1", project_id="proj/a", config=MagicMock()),
                AppContext(user_id="u1", project_id="proj_a", config=MagicMock()),
            ]
        )
        mock_cache = MagicMock(spec=DatusServiceCache)
        captured_keys = []

        async def fake_get_or_create(key, factory, expected_fingerprint=None):
            captured_keys.append(key)
            return await factory()

        mock_cache.get_or_create = AsyncMock(side_effect=fake_get_or_create)
        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._enterprise_extensions = EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        )

        with (
            patch("datus.api.deps.DatusService.compute_fingerprint", return_value="fp"),
            patch("datus.api.deps.DatusService") as mock_svc_cls,
        ):
            mock_svc_cls.compute_fingerprint = MagicMock(return_value="fp")
            mock_svc_cls.return_value = MagicMock()
            request_a = MagicMock()
            request_a.state = MagicMock()
            request_b = MagicMock()
            request_b.state = MagicMock()
            await get_datus_service(request_a)
            await get_datus_service(request_b)

        assert captured_keys[0] != captured_keys[1]
        assert captured_keys[0] == deps.service_cache_key("proj/a", enterprise_enabled=True)
        assert captured_keys[1] == deps.service_cache_key("proj_a", enterprise_enabled=True)
        assert mock_svc_cls.call_args_list[0].kwargs["project_id"] == "proj/a"
        assert mock_svc_cls.call_args_list[1].kwargs["project_id"] == "proj_a"

    async def test_auth_validation_error_returns_bad_request(self):
        """Auth-provider request validation errors are API 400s, not internal errors."""
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock(
            side_effect=DatusException(
                ErrorCode.COMMON_VALIDATION_FAILED,
                message="Invalid X-Datus-Principal header value: expected a JSON object.",
            )
        )
        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock()

        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache

        request = MagicMock()
        request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_datus_service(request)

        assert exc_info.value.status_code == 400
        assert "Invalid X-Datus-Principal header value" in exc_info.value.detail
        mock_cache.get_or_create.assert_not_called()

    async def test_no_fingerprint_when_config_is_none(self):
        """When ctx.config is None, expected_fingerprint passed as None."""
        mock_auth = MagicMock()
        ctx = AppContext(user_id="user-1", project_id="proj-1", config=None)
        mock_auth.authenticate = AsyncMock(return_value=ctx)

        mock_cache = MagicMock(spec=DatusServiceCache)
        mock_cache.get_or_create = AsyncMock(return_value=MagicMock())

        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache

        request = MagicMock()
        request.state = MagicMock()
        await get_datus_service(request)
        call_args = mock_cache.get_or_create.call_args
        assert call_args.kwargs["expected_fingerprint"] is None

    async def test_factory_propagates_default_source_and_interactive(self):
        """Factory passes module-level defaults through to DatusService constructor."""
        from unittest.mock import patch

        mock_auth = MagicMock()
        ctx = AppContext(user_id="u1", project_id="p1", config=MagicMock())
        mock_auth.authenticate = AsyncMock(return_value=ctx)

        mock_cache = MagicMock(spec=DatusServiceCache)
        captured = {}

        async def fake_get_or_create(key, factory, expected_fingerprint=None):
            captured["svc"] = await factory()
            return captured["svc"]

        mock_cache.get_or_create = AsyncMock(side_effect=fake_get_or_create)

        deps._auth_provider = mock_auth
        deps._service_cache = mock_cache
        deps._default_source = "web"
        deps._default_interactive = False

        request = MagicMock()
        request.state = MagicMock()

        with (
            patch("datus.api.deps.DatusService.compute_fingerprint", return_value="fp"),
            patch("datus.api.deps.DatusService") as mock_svc_cls,
        ):
            mock_svc_cls.compute_fingerprint = MagicMock(return_value="fp")
            mock_svc_cls.return_value = MagicMock()
            await get_datus_service(request)

        call_kwargs = mock_svc_cls.call_args.kwargs
        assert call_kwargs["default_source"] == "web"
        assert call_kwargs["default_interactive"] is False
        assert call_kwargs["project_id"] == "p1"

    async def test_factory_loads_config_when_none(self, real_agent_config):
        """Factory in get_datus_service loads config when ctx.config is None."""
        from datus.api.auth.no_auth_provider import NoAuthProvider
        from datus.api.services.datus_service import DatusService

        auth_provider = NoAuthProvider()
        cache = DatusServiceCache()
        deps._auth_provider = auth_provider
        deps._service_cache = cache
        deps._datasource = "test_ns"

        request = MagicMock()
        request.state = MagicMock()
        request.headers = {}
        # NoAuthProvider returns AppContext with config=None
        # Factory should call load_agent_config(datasource="test_ns")
        # This will fail because test_ns config doesn't exist in default paths,
        # but exercises the factory code path (lines 50-56)
        try:
            result = await get_datus_service(request)
            # If it succeeds, result should be a DatusService
            assert isinstance(result, DatusService)
        except RuntimeError as e:
            # Expected: config not found
            assert "Failed to load agent config" in str(e)
        finally:
            await cache.shutdown()

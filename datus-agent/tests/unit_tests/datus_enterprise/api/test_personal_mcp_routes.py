import asyncio
import copy
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    InMemoryUserMcpServerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
    SqliteUserMcpServerStore,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.downstream import StreamChatInput
from datus.utils.exceptions import DatusException
from datus_enterprise.api import personal_mcp_routes
from datus_enterprise.personal_mcp import validate_personal_mcp_destination, validate_personal_mcp_policy
from datus_enterprise.services.personal_mcp_chat import commit_personal_mcp_session, project_personal_mcp_for_chat

PERMISSIONS = {
    "module.mcp.personal",
    "mcp.personal.list",
    "mcp.personal.create",
    "mcp.personal.edit",
    "mcp.personal.remove",
    "mcp.personal.connectivity",
    "mcp.personal.tools",
}


def _agent_config():
    return SimpleNamespace(
        enterprise_config={
            "user_mcp": {
                "enabled": True,
                "allowed_hosts": ["*.example.com"],
                "max_servers_per_user": 3,
                "max_selected_per_session": 2,
            }
        }
    )


def _install(monkeypatch, store):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_mcp_server_store=store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(personal_mcp_routes.router)

    async def service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace(agent_config=_agent_config(), project_id="project")

    async def context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = service
    app.dependency_overrides[deps.get_request_app_context] = context
    return TestClient(app)


def test_personal_mcp_crud_is_owner_scoped_and_redacts_token(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    payload = {
        "display_name": "My Search",
        "transport": "http",
        "url": "https://mcp.example.com/api/mcp",
        "token": "alice-personal-secret",
        "blocked_tools": ["delete_document"],
    }

    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        created = client.post("/api/v1/me/mcp-servers", json=payload)
        mcp_id = created.json()["data"]["id"]
        listed = client.get("/api/v1/me/mcp-servers")

    assert created.status_code == 200
    assert created.json()["data"]["auth_mode"] == "static_bearer"
    assert created.json()["data"]["token_hint"] == "***cret"
    assert "alice-personal-secret" not in created.text
    assert "alice-personal-secret" not in listed.text

    with _client(AppContext(user_id="bob", permissions=PERMISSIONS)) as client:
        assert client.get("/api/v1/me/mcp-servers").json()["data"] == []
        assert client.get(f"/api/v1/me/mcp-servers/{mcp_id}").status_code == 404


def test_personal_mcp_delete_is_blocked_while_session_references_it(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    record = asyncio.run(
        store.put_server(
            user_id="alice",
            mcp_id="a" * 32,
            display_name="Search",
            transport="http",
            url="https://mcp.example.com/mcp",
            token=None,
            allowed_tools=[],
            blocked_tools=[],
            enabled=True,
        )
    )
    asyncio.run(
        store.set_session_binding(
            project_id="project",
            session_id="session-1",
            user_id="alice",
            servers=[{"mcp_id": record["id"], "revision": record["revision"]}],
        )
    )

    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.delete(f"/api/v1/me/mcp-servers/{record['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "PERSONAL_MCP_SERVER_IN_USE", "session_count": 1}
    assert asyncio.run(store.get_server("alice", record["id"])) is not None


def test_personal_mcp_connectivity_returns_tool_count(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    record = asyncio.run(
        store.put_server(
            user_id="alice",
            mcp_id="a" * 32,
            display_name="Search",
            transport="http",
            url="https://mcp.example.com/mcp",
            token=None,
            allowed_tools=[],
            blocked_tools=[],
            enabled=True,
        )
    )

    async def connected(*_args, **_kwargs):
        return True, "Connected", {"tool_count": 2}

    monkeypatch.setattr(personal_mcp_routes, "_operate", connected)
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.post(f"/api/v1/me/mcp-servers/{record['id']}/test")

    assert response.status_code == 200
    assert response.json()["data"] == {"connected": True, "message": "Connected", "tools_count": 2}


def test_personal_mcp_session_binding_is_restored_from_owner_scoped_store(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    asyncio.run(
        store.put_server(
            user_id="alice",
            mcp_id="a" * 32,
            display_name="My Search",
            transport="http",
            url="https://mcp.example.com/mcp",
            token=None,
            allowed_tools=[],
            blocked_tools=[],
            enabled=True,
        )
    )
    asyncio.run(
        store.set_session_binding(
            project_id="project",
            session_id="session-1",
            user_id="alice",
            servers=[{"mcp_id": "a" * 32, "revision": 2}],
        )
    )

    async def allow_session(*_args, **_kwargs):
        return SimpleNamespace(error=None)

    monkeypatch.setattr(personal_mcp_routes, "authorize_session_access", allow_session)
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.get("/api/v1/me/mcp-servers/session-binding/session-1")

    assert response.status_code == 200
    # The binding carries the user-facing display name so chat rendering can
    # resolve the runtime ``personal_<id>`` alias back to the MCP name.
    assert response.json()["data"] == {
        "session_id": "session-1",
        "servers": [{"mcp_id": "a" * 32, "revision": 2, "display_name": "My Search"}],
    }


def test_personal_mcp_session_binding_keeps_empty_display_name_for_deleted_server(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    asyncio.run(
        store.set_session_binding(
            project_id="project",
            session_id="session-1",
            user_id="alice",
            servers=[{"mcp_id": "b" * 32, "revision": 1}],
        )
    )

    async def allow_session(*_args, **_kwargs):
        return SimpleNamespace(error=None)

    monkeypatch.setattr(personal_mcp_routes, "authorize_session_access", allow_session)
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.get("/api/v1/me/mcp-servers/session-binding/session-1")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "session_id": "session-1",
        "servers": [{"mcp_id": "b" * 32, "revision": 1, "display_name": ""}],
    }


def test_personal_mcp_rejects_stdio_http_and_private_ip(monkeypatch):
    _install(monkeypatch, InMemoryUserMcpServerStore())
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        stdio = client.post(
            "/api/v1/me/mcp-servers",
            json={"display_name": "Local", "transport": "stdio", "url": "https://mcp.example.com"},
        )
        insecure = client.post(
            "/api/v1/me/mcp-servers",
            json={"display_name": "HTTP", "transport": "http", "url": "http://mcp.example.com"},
        )

    assert stdio.status_code == 422
    assert insecure.status_code == 400
    with pytest.raises(DatusException, match="not public"):
        validate_personal_mcp_policy(
            SimpleNamespace(enterprise_config={"user_mcp": {"enabled": True, "allowed_hosts": ["127.0.0.1"]}}),
            url="https://127.0.0.1/mcp",
        )


@pytest.mark.asyncio
async def test_destination_validation_rejects_dns_to_private_address(monkeypatch):
    monkeypatch.setattr(
        "datus_enterprise.personal_mcp.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("10.0.0.8", 0))],
    )
    with pytest.raises(DatusException, match="not public"):
        await validate_personal_mcp_destination("https://mcp.example.com/mcp")


@pytest.mark.asyncio
async def test_session_selection_is_immutable():
    store = InMemoryUserMcpServerStore()
    first = [{"mcp_id": "a" * 32, "revision": 1}]
    await store.set_session_binding(project_id="p", session_id="s", user_id="alice", servers=first)
    binding = await store.get_session_binding("p", "s", "alice")
    assert binding is not None
    assert binding["servers"] == first
    with pytest.raises(DatusException, match="locked"):
        await store.set_session_binding(
            project_id="p",
            session_id="s",
            user_id="alice",
            servers=[{"mcp_id": "b" * 32, "revision": 1}],
        )
    assert await store.get_session_binding("p", "s", "bob") is None
    assert await store.count_session_bindings("alice", "a" * 32) == 1
    assert await store.delete_session_binding("p", "s", "bob") is False
    assert await store.delete_session_binding("p", "s", "alice") is True
    assert await store.count_session_bindings("alice", "a" * 32) == 0


@pytest.mark.asyncio
async def test_sqlite_store_encrypts_token(tmp_path):
    db_path = tmp_path / "enterprise.db"
    store = SqliteUserMcpServerStore(str(db_path), encryption_secret="x" * 32)
    await store.put_server(
        user_id="alice",
        mcp_id="a" * 32,
        display_name="Search",
        transport="http",
        url="https://mcp.example.com/mcp",
        token="private-token",
        allowed_tools=[],
        blocked_tools=[],
        enabled=True,
    )
    assert b"private-token" not in db_path.read_bytes()
    record = await store.get_server("alice", "a" * 32)
    assert record is not None
    assert record["token"] == "private-token"

    await store.set_session_binding(
        project_id="project",
        session_id="session-1",
        user_id="alice",
        servers=[{"mcp_id": record["id"], "revision": record["revision"]}],
    )
    assert await store.count_session_bindings("alice", record["id"]) == 1
    assert await store.delete_session_binding("project", "session-1", "alice") is True
    assert await store.count_session_bindings("alice", record["id"]) == 0


@pytest.mark.asyncio
async def test_chat_projection_attaches_only_owned_selected_mcp(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    monkeypatch.setattr(
        "datus_enterprise.services.personal_mcp_chat.validate_personal_mcp_destination",
        lambda _url, **_kwargs: _completed(),
    )
    record = await store.put_server(
        user_id="alice",
        mcp_id="a" * 32,
        display_name="Search",
        transport="http",
        url="https://mcp.example.com/mcp",
        token="private-token",
        allowed_tools=[],
        blocked_tools=["delete_document"],
        enabled=True,
    )
    agent_record = {
        "agent_id": "chat_custom",
        "node_class": "chat",
        "scoped_context": {"_enterprise_agent_policy": {"personal_mcp_mode": "selectable"}},
    }
    config = _agent_config()
    config.agentic_nodes = {
        "chat_custom": {
            "id": "chat_custom",
            "mcp": "enterprise_search",
            "tool_policy": {"mode": "allowlist", "allowed": ["mcp.enterprise_search.*"], "denied": []},
        },
        "child": {"id": "child", "mcp": "enterprise_child"},
    }
    shared_config = copy.deepcopy(config)
    request = StreamChatInput(
        message="search",
        session_id="chat_custom_session_1",
        subagent_id="chat_custom",
        personal_mcp_ids=[record["id"]],
    )

    projected = await project_personal_mcp_for_chat(
        AppContext(user_id="alice", permissions=PERMISSIONS | {"mcp.personal.use"}),
        request,
        agent_config=config,
        agent_record=agent_record,
        project_id="project",
        new_session=True,
    )

    alias = f"personal_{record['id']}"
    assert [item["id"] for item in projected] == [record["id"]]
    assert alias in config._request_mcp_servers
    # The projection keeps the user-facing display name next to the runtime
    # alias so chat rendering never shows the record ID in tool cards.
    assert config._request_mcp_display_names == {alias: "Search"}
    assert alias in config.agentic_nodes["chat_custom"]["mcp"]
    assert f"mcp.{alias}.*" in config.agentic_nodes["chat_custom"]["tool_policy"]["allowed"]
    assert config.agentic_nodes["child"] == {"id": "child", "mcp": "enterprise_child"}
    assert not hasattr(shared_config, "_request_mcp_servers")
    assert not hasattr(shared_config, "_request_mcp_display_names")
    assert shared_config.agentic_nodes["chat_custom"]["mcp"] == "enterprise_search"
    binding = await store.get_session_binding("project", "chat_custom_session_1", "alice")
    assert binding is None

    await commit_personal_mcp_session(
        project_id="project",
        session_id="chat_custom_session_1",
        user_id="alice",
        records=projected,
    )
    binding = await store.get_session_binding("project", "chat_custom_session_1", "alice")
    assert binding is not None
    assert binding["servers"] == [{"mcp_id": record["id"], "revision": 1}]


@pytest.mark.asyncio
async def test_chat_projection_enforces_use_permission_agent_mode_and_owner(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    monkeypatch.setattr(
        "datus_enterprise.services.personal_mcp_chat.validate_personal_mcp_destination",
        lambda _url, **_kwargs: _completed(),
    )
    record = await store.put_server(
        user_id="alice",
        mcp_id="a" * 32,
        display_name="Search",
        transport="http",
        url="https://mcp.example.com/mcp",
        token=None,
        allowed_tools=[],
        blocked_tools=[],
        enabled=True,
    )
    config = _agent_config()
    config.agentic_nodes = {"chat_custom": {"id": "chat_custom", "mcp": ""}}
    request = StreamChatInput(
        message="search",
        subagent_id="chat_custom",
        personal_mcp_ids=[record["id"]],
    )
    selectable = {
        "agent_id": "chat_custom",
        "scoped_context": {"_enterprise_agent_policy": {"personal_mcp_mode": "selectable"}},
    }

    with pytest.raises(HTTPException, match="missing permission mcp.personal.use"):
        await project_personal_mcp_for_chat(
            AppContext(user_id="alice", permissions=PERMISSIONS),
            request,
            agent_config=copy.deepcopy(config),
            agent_record=selectable,
            project_id="project",
            new_session=True,
        )

    with pytest.raises(HTTPException, match="PERSONAL_MCP_AGENT_DISABLED"):
        await project_personal_mcp_for_chat(
            AppContext(user_id="alice", permissions=PERMISSIONS | {"mcp.personal.use"}),
            request,
            agent_config=copy.deepcopy(config),
            agent_record={"agent_id": "chat_custom", "scoped_context": {}},
            project_id="project",
            new_session=True,
        )

    with pytest.raises(HTTPException, match="PERSONAL_MCP_NOT_FOUND"):
        await project_personal_mcp_for_chat(
            AppContext(user_id="bob", permissions=PERMISSIONS | {"mcp.personal.use"}),
            request,
            agent_config=copy.deepcopy(config),
            agent_record=selectable,
            project_id="project",
            new_session=True,
        )


@pytest.mark.asyncio
async def test_chat_projection_rechecks_current_allowed_hosts(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    monkeypatch.setattr(
        "datus_enterprise.services.personal_mcp_chat.validate_personal_mcp_destination",
        lambda _url, **_kwargs: _completed(),
    )
    record = await store.put_server(
        user_id="alice",
        mcp_id="a" * 32,
        display_name="Search",
        transport="http",
        url="https://mcp.example.com/mcp",
        token=None,
        allowed_tools=[],
        blocked_tools=[],
        enabled=True,
    )
    config = _agent_config()
    config.enterprise_config["user_mcp"]["allowed_hosts"] = ["approved.example.net"]
    config.agentic_nodes = {"chat_custom": {"id": "chat_custom", "mcp": ""}}

    with pytest.raises(HTTPException, match="PERSONAL_MCP_DESTINATION_DENIED"):
        await project_personal_mcp_for_chat(
            AppContext(user_id="alice", permissions=PERMISSIONS | {"mcp.personal.use"}),
            StreamChatInput(
                message="search",
                subagent_id="chat_custom",
                personal_mcp_ids=[record["id"]],
            ),
            agent_config=config,
            agent_record={
                "agent_id": "chat_custom",
                "scoped_context": {"_enterprise_agent_policy": {"personal_mcp_mode": "selectable"}},
            },
            project_id="project",
            new_session=True,
        )


@pytest.mark.asyncio
async def test_existing_session_rejects_selection_change_and_revision_change(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    monkeypatch.setattr(
        "datus_enterprise.services.personal_mcp_chat.validate_personal_mcp_destination",
        lambda _url, **_kwargs: _completed(),
    )
    record = await store.put_server(
        user_id="alice",
        mcp_id="a" * 32,
        display_name="Search",
        transport="http",
        url="https://mcp.example.com/mcp",
        token=None,
        allowed_tools=[],
        blocked_tools=[],
        enabled=True,
    )
    await store.set_session_binding(
        project_id="project",
        session_id="session-1",
        user_id="alice",
        servers=[{"mcp_id": record["id"], "revision": 1}],
    )
    config = _agent_config()
    config.agentic_nodes = {"chat_custom": {"id": "chat_custom", "mcp": ""}}
    agent_record = {
        "agent_id": "chat_custom",
        "scoped_context": {"_enterprise_agent_policy": {"personal_mcp_mode": "selectable"}},
    }
    ctx = AppContext(user_id="alice", permissions=PERMISSIONS | {"mcp.personal.use"})

    with pytest.raises(HTTPException, match="PERSONAL_MCP_SESSION_LOCKED"):
        await project_personal_mcp_for_chat(
            ctx,
            StreamChatInput(
                message="search",
                session_id="session-1",
                subagent_id="chat_custom",
                personal_mcp_ids=["b" * 32],
            ),
            agent_config=copy.deepcopy(config),
            agent_record=agent_record,
            project_id="project",
            new_session=False,
        )

    await store.put_server(
        user_id="alice",
        mcp_id=record["id"],
        display_name="Search v2",
        transport="http",
        url="https://mcp.example.com/mcp",
        token=None,
        allowed_tools=[],
        blocked_tools=[],
        enabled=True,
    )
    with pytest.raises(HTTPException, match="PERSONAL_MCP_REVISION_CHANGED"):
        await project_personal_mcp_for_chat(
            ctx,
            StreamChatInput(message="search", session_id="session-1", subagent_id="chat_custom"),
            agent_config=copy.deepcopy(config),
            agent_record=agent_record,
            project_id="project",
            new_session=False,
        )


@pytest.mark.asyncio
async def test_destination_validation_allows_private_address_when_configured(monkeypatch):
    monkeypatch.setattr(
        "datus_enterprise.personal_mcp.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("10.0.0.8", 0))],
    )
    # 默认严格模式仍然拒绝私网解析结果。
    with pytest.raises(DatusException, match="not public"):
        await validate_personal_mcp_destination("https://mcp.example.com/mcp")
    # 显式开启 allow_private_hosts 后放行（连接前 DNS 复查仍然执行）。
    await validate_personal_mcp_destination("https://mcp.example.com/mcp", allow_private_hosts=True)


def _config_with_mcp_flags(*, allow_insecure_http: bool = False, allow_private_hosts: bool = False):
    return SimpleNamespace(
        enterprise_config={
            "user_mcp": {
                "enabled": True,
                "allowed_hosts": ["*.example.com", "127.0.0.1"],
                "allow_insecure_http": allow_insecure_http,
                "allow_private_hosts": allow_private_hosts,
            }
        }
    )


def test_personal_mcp_policy_flags_open_http_and_private_hosts_independently():
    # 两个开关都关闭：https 明文 URL 被拒、私网被拒（既有契约）。
    strict = _config_with_mcp_flags()
    with pytest.raises(DatusException, match="must use HTTPS"):
        validate_personal_mcp_policy(strict, url="http://mcp.example.com/mcp")
    with pytest.raises(DatusException, match="not public"):
        validate_personal_mcp_policy(strict, url="https://127.0.0.1/mcp")

    # 只开 allow_insecure_http：允许公网明文 HTTP，但私网仍然被拒。
    insecure = _config_with_mcp_flags(allow_insecure_http=True)
    assert validate_personal_mcp_policy(insecure, url="http://mcp.example.com/mcp") == "http://mcp.example.com/mcp"
    assert validate_personal_mcp_policy(insecure, url="https://mcp.example.com/mcp").startswith("https://")
    with pytest.raises(DatusException, match="not public"):
        validate_personal_mcp_policy(insecure, url="https://127.0.0.1/mcp")

    # 只开 allow_private_hosts：允许私网 HTTPS，但明文 HTTP 仍然被拒。
    private = _config_with_mcp_flags(allow_private_hosts=True)
    assert validate_personal_mcp_policy(private, url="https://127.0.0.1/mcp") == "https://127.0.0.1/mcp"
    with pytest.raises(DatusException, match="must use HTTPS"):
        validate_personal_mcp_policy(private, url="http://127.0.0.1/mcp")

    # 两个开关都打开：明文 + 私网均可；白名单仍然生效。
    relaxed = _config_with_mcp_flags(allow_insecure_http=True, allow_private_hosts=True)
    assert validate_personal_mcp_policy(relaxed, url="http://127.0.0.1/mcp") == "http://127.0.0.1/mcp"
    with pytest.raises(DatusException, match="host is not allowed"):
        validate_personal_mcp_policy(relaxed, url="http://unapproved.example.net/mcp")


def test_personal_mcp_policy_mode_labels():
    from datus_enterprise.personal_mcp import personal_mcp_policy_mode

    assert personal_mcp_policy_mode(_agent_config()) == "strict"
    assert personal_mcp_policy_mode(_config_with_mcp_flags(allow_insecure_http=True)) == "insecure_http"
    assert personal_mcp_policy_mode(_config_with_mcp_flags(allow_private_hosts=True)) == "private_hosts"
    assert (
        personal_mcp_policy_mode(_config_with_mcp_flags(allow_insecure_http=True, allow_private_hosts=True))
        == "relaxed"
    )


def test_personal_mcp_api_allows_http_when_configured(monkeypatch):
    store = InMemoryUserMcpServerStore()
    _install(monkeypatch, store)
    base_config = _agent_config

    def relaxed_config():
        config = base_config()
        config.enterprise_config["user_mcp"]["allow_insecure_http"] = True
        return config

    monkeypatch.setattr(sys.modules[__name__], "_agent_config", relaxed_config)
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        created = client.post(
            "/api/v1/me/mcp-servers",
            json={"display_name": "HTTP", "transport": "http", "url": "http://mcp.example.com/mcp"},
        )

    assert created.status_code == 200
    assert created.json()["data"]["url"] == "http://mcp.example.com/mcp"


def test_personal_mcp_options_expose_network_policy_flags(monkeypatch):
    _install(monkeypatch, InMemoryUserMcpServerStore())
    base_config = _agent_config

    def relaxed_config():
        config = base_config()
        config.enterprise_config["user_mcp"]["allow_insecure_http"] = True
        config.enterprise_config["user_mcp"]["allow_private_hosts"] = True
        return config

    monkeypatch.setattr(sys.modules[__name__], "_agent_config", relaxed_config)
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.get("/api/v1/me/mcp-servers/options")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["allow_insecure_http"] is True
    assert data["allow_private_hosts"] is True
    assert "timeout_seconds" not in data


def test_personal_mcp_options_default_to_strict(monkeypatch):
    _install(monkeypatch, InMemoryUserMcpServerStore())
    with _client(AppContext(user_id="alice", permissions=PERMISSIONS)) as client:
        response = client.get("/api/v1/me/mcp-servers/options")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["allow_insecure_http"] is False
    assert data["allow_private_hosts"] is False


async def _completed():
    return None

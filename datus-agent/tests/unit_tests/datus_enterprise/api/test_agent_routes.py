from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseAgentStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.routes import chat_routes
from datus_enterprise.api import agent_routes
from datus_enterprise.postgres_stores import _agent_record, _normalized_agent_metadata


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _install_extensions(monkeypatch, agent_store, audit_sink=None, *, enabled=False):
    extensions = EnterpriseExtensions(
        enabled=enabled,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
        agent_store=agent_store,
    )
    monkeypatch.setattr(deps, "_enterprise_extensions", extensions)
    monkeypatch.setattr(agent_routes.deps, "_enterprise_extensions", extensions)
    return extensions


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(agent_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_admin_agents_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents")

    assert response.status_code == 403
    assert "module.admin.agents" in response.json()["detail"]


def test_admin_agent_upsert_acl_and_available_list(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, agent_store, audit_sink)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        upsert_response = client.put(
            "/api/v1/admin/agents/sales_sql",
            json={
                "name": "Sales SQL",
                "node_class": "gen_sql",
                "status": "published",
                "tools": ["db_tools.read_query"],
                "acl": {"visibility": "enterprise"},
            },
        )
        acl_response = client.get("/api/v1/admin/agents/sales_sql/acl")

    assert upsert_response.status_code == 200
    assert upsert_response.json()["success"] is True
    assert upsert_response.json()["data"]["agent_id"] == "sales_sql"
    assert acl_response.json()["data"]["visibility"] == "enterprise"
    assert audit_sink.events[-2].action == "module.admin.agents"
    assert audit_sink.events[-2].metadata["operation"] == "upsert_admin_agent"

    analyst_ctx = AppContext(user_id="alice", permissions={"module.chat", "module.sql_executor"})
    with _client(analyst_ctx) as client:
        list_response = client.get("/api/v1/agents")

    ids = {item["agent_id"] for item in list_response.json()["data"]}
    assert "sales_sql" in ids


def test_available_agents_filters_node_class_permission(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    agent_store._agents["sales_sql"] = {
        "agent_id": "sales_sql",
        "node_class": "gen_sql",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.get("/api/v1/agents")

    ids = {item["agent_id"] for item in response.json()["data"]}
    assert "sales_sql" not in ids


def test_admin_agent_upsert_rejects_runtime_unsupported_chat_node_class(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put("/api/v1/admin/agents/custom_chat", json={"node_class": "chat"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "AGENT_INVALID"
    assert agent_store._agents == {}


def test_admin_agent_upsert_is_blocked_in_readonly_status(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, agent_store, audit_sink, enabled=True)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.put("/api/v1/admin/agents/sales_sql", json={"status": "published"})

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    assert agent_store._agents == {}
    assert audit_sink.events[-1].action == "system.platform_status"
    assert audit_sink.events[-1].resource_type == "agent"


def test_enterprise_agent_materializes_into_request_scoped_config():
    agent_config = SimpleNamespace(agentic_nodes={})
    record = {
        "agent_id": "sales_sql",
        "node_class": "gen_sql",
        "status": "published",
        "description": "Sales SQL",
        "tools": ["db_tools.read_query"],
        "acl": {"visibility": "enterprise"},
    }

    chat_routes._materialize_enterprise_agent(agent_config, record)

    assert "sales_sql" in agent_config.agentic_nodes
    entry = agent_config.agentic_nodes["sales_sql"]
    assert entry["id"] == "sales_sql"
    assert entry["node_class"] == "gen_sql"
    assert entry["tools"] == "db_tools.read_query"


def test_pg_agent_store_helpers_preserve_runtime_record_shape():
    payload = _normalized_agent_metadata(
        {
            "agent_id": "sales_sql",
            "node_class": "gen_sql",
            "status": "published",
            "tools": "semantic_tools.list_metrics,db_tools.read_query",
            "scoped_context": {"tables": ["sales.orders"]},
            "acl": {"visibility": "role", "allowed_roles": ["analyst", "analyst"]},
        }
    )
    assert payload["tools"] == ["db_tools.read_query", "semantic_tools.list_metrics"]
    assert payload["acl"] == {
        "visibility": "role",
        "allowed_roles": ["analyst"],
        "allowed_user_ids": [],
    }

    record = _agent_record(
        {
            "agent_id": payload["agent_id"],
            "name": payload["name"],
            "description": payload["description"],
            "node_class": payload["node_class"],
            "status": payload["status"],
            "owner_user_id": payload["owner_user_id"],
            "datasource_id": payload["datasource_id"],
            "artifact_slug": payload["artifact_slug"],
            "prompt_template": payload["prompt_template"],
            "prompt_language": payload["prompt_language"],
            "prompt_version": payload["prompt_version"],
            "tools": payload["tools"],
            "mcp": payload["mcp"],
            "skills": payload["skills"],
            "scoped_context_json": payload["scoped_context"],
            "rules": payload["rules"],
            "max_turns": payload["max_turns"],
            "acl_json": payload["acl"],
            "created_at": None,
            "updated_at": None,
        }
    )

    assert record["agent_id"] == "sales_sql"
    assert record["node_class"] == "gen_sql"
    assert record["status"] == "published"
    assert record["scoped_context"] == {"tables": ["sales.orders"]}
    assert record["acl"]["visibility"] == "role"

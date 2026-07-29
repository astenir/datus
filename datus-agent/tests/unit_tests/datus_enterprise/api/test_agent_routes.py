import argparse
import asyncio
from types import SimpleNamespace

import pytest
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
from datus.api.service import create_app
from datus_enterprise.agent_registry import (
    ENTERPRISE_AGENT_NODE_CAPABILITIES,
    ENTERPRISE_AGENT_NODE_CLASSES,
    materialize_enterprise_agent,
)
from datus_enterprise.api import agent_routes
from datus_enterprise.postgres_stores import _agent_record, _normalized_agent_metadata


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def test_create_app_registers_authoritative_legacy_agent_routes_once():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    list_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/agent/list" and "GET" in getattr(route, "methods", set())
    ]

    assert len(list_routes) == 1
    assert list_routes[0].endpoint.__module__ == "datus_enterprise.api.legacy_agent_routes"


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


def test_admin_agent_tools_and_tool_reference(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        catalog_response = client.get("/api/v1/admin/agents/tools")
        reference_response = client.get("/api/v1/admin/agents/tool-reference", params={"node_class": "gen_sql"})
        visual_reference_response = client.get(
            "/api/v1/admin/agents/tool-reference",
            params={"node_class": "gen_visual_report"},
        )

    assert catalog_response.status_code == 200
    assert catalog_response.json()["success"] is True
    assert "db_tools" in catalog_response.json()["data"]["tools"]
    assert catalog_response.json()["data"]["tools"]["tools"] == [
        "ask_user",
        "confirm_plan",
        "todo_list",
        "todo_read",
        "todo_update",
        "todo_write",
    ]
    assert catalog_response.json()["data"]["tools"]["artifact_tools"] == [
        "bind_existing_dashboard",
        "bind_existing_report",
        "save_query",
        "save_query_template",
        "start_new_dashboard",
        "start_new_report",
        "validate_render",
    ]
    assert reference_response.status_code == 200
    assert reference_response.json()["success"] is True
    assert "db_tools.*" in reference_response.json()["data"]["default_tools"]
    assert "db_tools" in reference_response.json()["data"]["tool_types"]
    assert "tools.*" in reference_response.json()["data"]["default_tools"]
    assert reference_response.json()["data"]["tool_types"]["tools"]["tools"] == [
        "ask_user",
        "confirm_plan",
        "todo_list",
        "todo_read",
        "todo_update",
        "todo_write",
    ]
    assert visual_reference_response.status_code == 200
    assert visual_reference_response.json()["data"]["tool_types"]["artifact_tools"]["tools"] == [
        "start_new_report",
        "bind_existing_report",
        "save_query",
        "validate_render",
    ]
    assert "artifact_tools.start_new_report" in visual_reference_response.json()["data"]["default_tools"]
    assert "filesystem_tools.write_file" in visual_reference_response.json()["data"]["default_tools"]


def test_admin_agent_node_types(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents/node-types")

    assert response.status_code == 200
    assert response.json()["success"] is True
    items = response.json()["data"]
    assert [item["node_class"] for item in items] == [
        "chat",
        "gen_sql",
        "gen_report",
        "gen_visual_report",
        "gen_visual_dashboard",
        "ask_metrics",
        "ask_report",
        "ask_dashboard",
    ]
    assert {item["node_class"] for item in items} == ENTERPRISE_AGENT_NODE_CLASSES
    assert all(item["label"] and item["description"] for item in items)
    assert {item["node_class"] for item in items if item["supports_mcp"]} == {"chat", "gen_sql"}
    assert all(capability.enterprise_visible for capability in ENTERPRISE_AGENT_NODE_CAPABILITIES)


def test_admin_agent_node_types_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents/node-types")

    assert response.status_code == 403
    assert "module.admin.agents" in response.json()["detail"]


def test_admin_agent_acl_directories_use_agent_permission_and_return_sanitized_records(monkeypatch):
    audit_sink = CollectingAuditSink()
    extensions = _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore(), audit_sink)
    extensions.user_store._users.update(
        {
            "alice": {
                "user_id": "alice",
                "display_name": "Alice Chen",
                "email": "alice@example.com",
                "enabled": True,
                "department": "Finance",
                "title": "Analyst",
            },
            "disabled": {
                "user_id": "disabled",
                "display_name": "Disabled User",
                "email": None,
                "enabled": False,
            },
        }
    )
    extensions.role_store._roles.update(
        {
            "analyst": {
                "role_id": "analyst",
                "name": "Analyst",
                "description": "Read-only analysts",
                "permissions": ["module.chat"],
                "built_in": False,
            },
            "operator": {
                "role_id": "operator",
                "name": "Operator",
                "description": None,
                "permissions": ["module.admin.*"],
                "built_in": False,
            },
        }
    )
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        users_response = client.get("/api/v1/admin/agents/acl-users", params={"query": "alice"})
        roles_response = client.get("/api/v1/admin/agents/acl-roles", params={"query": "analyst"})

    assert users_response.status_code == 200
    assert users_response.json()["data"] == [
        {
            "user_id": "alice",
            "display_name": "Alice Chen",
            "email": "alice@example.com",
            "department": "Finance",
            "title": "Analyst",
        }
    ]
    assert roles_response.status_code == 200
    assert roles_response.json()["data"] == [
        {
            "role_id": "analyst",
            "name": "Analyst",
            "description": "Read-only analysts",
        }
    ]
    assert audit_sink.events[-2].metadata["operation"] == "list_admin_agent_acl_users"
    assert audit_sink.events[-1].metadata["operation"] == "list_admin_agent_acl_roles"


def test_admin_agent_acl_directories_reject_without_agent_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.users", "module.admin.roles"})

    with _client(ctx) as client:
        users_response = client.get("/api/v1/admin/agents/acl-users")
        roles_response = client.get("/api/v1/admin/agents/acl-roles")

    assert users_response.status_code == 403
    assert roles_response.status_code == 403
    assert "module.admin.agents" in users_response.json()["detail"]
    assert "module.admin.agents" in roles_response.json()["detail"]


def test_admin_agents_list_includes_readonly_builtins(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    agent_store._agents["sales_sql"] = {
        "agent_id": "sales_sql",
        "node_class": "gen_sql",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents")

    assert response.status_code == 200
    items = {item["agent_id"]: item for item in response.json()["data"]}
    assert items["chat"]["source"] == "builtin"
    assert items["chat"]["node_class"] == "chat"
    assert items["gen_sql"]["source"] == "builtin"
    assert items["gen_sql"]["status"] == "disabled"
    assert items["gen_sql"]["acl"]["visibility"] == "private"
    assert "feedback" not in items
    assert items["sales_sql"]["source"] == "enterprise"
    assert items["sales_sql"]["acl"]["visibility"] == "enterprise"


def test_admin_agents_status_filter_treats_builtins_as_published(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        published_response = client.get("/api/v1/admin/agents", params={"status": "published"})
        draft_response = client.get("/api/v1/admin/agents", params={"status": "draft"})

    published_ids = {item["agent_id"] for item in published_response.json()["data"]}
    draft_ids = {item["agent_id"] for item in draft_response.json()["data"]}
    assert "chat" in published_ids
    assert "gen_sql" not in published_ids
    assert "gen_sql" not in draft_ids


def test_admin_builtin_agent_detail_is_readonly(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        detail_response = client.get("/api/v1/admin/agents/gen_sql")
        mutation_response = client.put("/api/v1/admin/agents/gen_sql", json={"status": "published"})

    assert detail_response.status_code == 200
    assert detail_response.json()["success"] is True
    assert detail_response.json()["data"]["source"] == "builtin"
    assert detail_response.json()["data"]["acl"]["visibility"] == "private"
    assert detail_response.json()["data"]["prompt_template_name"] == "gen_sql_system"
    assert detail_response.json()["data"]["prompt_version"] == "1.2"
    assert (
        detail_response.json()["data"]["prompt_template"] == detail_response.json()["data"]["prompt_template_content"]
    )
    assert "available_tool_names" in detail_response.json()["data"]["prompt_template"]
    assert mutation_response.status_code == 200
    assert mutation_response.json()["success"] is False
    assert mutation_response.json()["errorCode"] == "AGENT_ID_INVALID"


def test_admin_builtin_agent_detail_uses_special_template_mapping(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents/gen_skill")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["prompt_template_name"] == "skill_creator_system"
    assert response.json()["data"]["prompt_version"] == "1.0"
    assert "skill engineer" in response.json()["data"]["prompt_template"]


def test_admin_default_chat_agent_detail_is_readonly(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        detail_response = client.get("/api/v1/admin/agents/chat")
        mutation_response = client.put("/api/v1/admin/agents/chat", json={"node_class": "chat"})

    assert detail_response.status_code == 200
    assert detail_response.json()["success"] is True
    assert detail_response.json()["data"]["source"] == "builtin"
    assert detail_response.json()["data"]["node_class"] == "chat"
    assert detail_response.json()["data"]["prompt_template_name"] == "chat_system"
    assert mutation_response.status_code == 200
    assert mutation_response.json()["success"] is False
    assert mutation_response.json()["errorCode"] == "AGENT_ID_INVALID"


def test_available_agent_tools_require_visible_agent_acl_not_node_permission(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    agent_store._agents["sales_sql"] = {
        "agent_id": "sales_sql",
        "node_class": "gen_sql",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }

    analyst_ctx = AppContext(user_id="alice", permissions={"module.chat", "module.sql_executor"})
    with _client(analyst_ctx) as client:
        response = client.get("/api/v1/agents/sales_sql/tools")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "semantic_tools.*" in response.json()["data"]["default_tools"]

    chat_only_ctx = AppContext(user_id="bob", permissions={"module.chat"})
    with _client(chat_only_ctx) as client:
        allowed_response = client.get("/api/v1/agents/sales_sql/tools")

    assert allowed_response.status_code == 200
    assert allowed_response.json()["success"] is True


def test_available_default_chat_agent_is_listed_and_readable(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        list_response = client.get("/api/v1/agents")
        detail_response = client.get("/api/v1/agents/chat")
        tools_response = client.get("/api/v1/agents/chat/tools")

    ids = {item["agent_id"] for item in list_response.json()["data"]}
    assert "chat" in ids
    assert detail_response.json()["success"] is True
    assert detail_response.json()["data"]["source"] == "builtin"
    assert tools_response.json()["success"] is True
    assert "memory_tools.*" in tools_response.json()["data"]["default_tools"]


def test_available_builtin_agents_use_persisted_acl_overlay_not_module_permissions(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())

    chat_ctx = AppContext(user_id="alice", permissions={"module.chat"})
    with _client(chat_ctx) as client:
        chat_response = client.get("/api/v1/agents")

    chat_builtin_ids = {item["agent_id"] for item in chat_response.json()["data"] if item["source"] == "builtin"}
    assert chat_builtin_ids == {"chat"}

    privileged_ctx = AppContext(user_id="operator", permissions={"*"})
    with _client(privileged_ctx) as client:
        privileged_response = client.get("/api/v1/agents")

    privileged_builtin_ids = {
        item["agent_id"] for item in privileged_response.json()["data"] if item["source"] == "builtin"
    }
    assert privileged_builtin_ids == {"chat"}


def test_user_can_persist_and_read_visible_default_agent(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    extensions = _install_extensions(monkeypatch, agent_store)
    agent_store._agents["sales_sql"] = {
        "agent_id": "sales_sql",
        "name": "Sales SQL",
        "node_class": "gen_sql",
        "status": "published",
        "owner_user_id": "operator",
        "acl": {"visibility": "enterprise"},
    }
    ctx = AppContext(user_id="alice", permissions={"module.chat", "module.sql_executor"})

    with _client(ctx) as client:
        update_response = client.put(
            "/api/v1/me/agent-preferences",
            json={"default_agent_id": "sales_sql"},
        )
        read_response = client.get("/api/v1/me/agent-preferences")

    assert update_response.status_code == 200
    assert update_response.json()["data"]["default_agent_id"] == "sales_sql"
    assert read_response.json()["data"]["default_agent_id"] == "sales_sql"
    assert extensions.user_store._chat_preferences["alice"]["default_agent_id"] == "sales_sql"


def test_user_agent_preference_rejects_unavailable_agent_and_falls_back_when_disabled(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    agent_store._agents["private_sql"] = {
        "agent_id": "private_sql",
        "name": "Private SQL",
        "node_class": "gen_sql",
        "status": "published",
        "owner_user_id": "bob",
        "acl": {"visibility": "private"},
    }
    agent_store._agents["sales_sql"] = {
        "agent_id": "sales_sql",
        "name": "Sales SQL",
        "node_class": "gen_sql",
        "status": "published",
        "owner_user_id": "operator",
        "acl": {"visibility": "enterprise"},
    }
    ctx = AppContext(user_id="alice", permissions={"module.chat", "module.sql_executor"})

    with _client(ctx) as client:
        denied_response = client.put(
            "/api/v1/me/agent-preferences",
            json={"default_agent_id": "private_sql"},
        )
        saved_response = client.put(
            "/api/v1/me/agent-preferences",
            json={"default_agent_id": "sales_sql"},
        )
        agent_store._agents["sales_sql"]["status"] = "disabled"
        fallback_response = client.get("/api/v1/me/agent-preferences")

    assert denied_response.json()["success"] is False
    assert denied_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert saved_response.json()["success"] is True
    assert fallback_response.json()["data"]["default_agent_id"] == "chat"
    assert fallback_response.json()["data"]["source"] == "builtin_chat"


def test_user_can_clear_default_agent_preference_and_stably_fall_back_to_chat(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["ask_metrics"] = {
        "agent_id": "ask_metrics",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.put("/api/v1/me/agent-preferences", json={"default_agent_id": None})

    assert response.status_code == 200
    assert response.json()["data"]["default_agent_id"] == "chat"
    assert response.json()["data"]["source"] == "builtin_chat"
    assert response.json()["data"]["user_default_agent_id"] is None


def test_default_agent_falls_back_to_first_acl_available_when_chat_is_disabled(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["ask_metrics"] = {
        "agent_id": "ask_metrics",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }
    agent_store._agents["chat"] = {
        "agent_id": "chat",
        "status": "disabled",
        "acl": {"visibility": "enterprise"},
    }
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.get("/api/v1/me/agent-preferences")

    assert response.status_code == 200
    assert response.json()["data"]["default_agent_id"] == "ask_metrics"
    assert response.json()["data"]["source"] == "first_available"


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


def test_available_agents_do_not_filter_by_node_class_permission(monkeypatch):
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
    assert "sales_sql" in ids


def test_admin_agent_upsert_accepts_custom_chat_node_class(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/custom_chat",
            json={
                "name": "Custom Chat",
                "node_class": "chat",
                "status": "published",
                "mcp": ["filesystem"],
                "tool_policy": {"mode": "allowlist", "allowed": []},
                "acl": {"visibility": "enterprise"},
            },
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["node_class"] == "chat"
    assert response.json()["data"]["mcp"] == ["filesystem"]
    assert response.json()["data"]["tool_policy"]["allowed"] == ["mcp.filesystem.*"]
    assert agent_store._agents["custom_chat"]["node_class"] == "chat"


@pytest.mark.parametrize(
    ("tool_policy", "expected_message"),
    [
        ({"mode": "allowlist", "allowed": ["unknown_tools.*"]}, "Invalid allowed tools"),
        ({"mode": "allowlist", "allowed": ["bash_tools.*"]}, "Invalid allowed tools"),
        ({"mode": "allowlist", "denied": ["unknown_tools.*"]}, "Invalid denied tools"),
    ],
)
def test_admin_agent_upsert_rejects_invalid_tool_policy_patterns(
    monkeypatch,
    tool_policy,
    expected_message,
):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/invalid_policy",
            json={"node_class": "chat", "tool_policy": tool_policy},
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert expected_message in response.json()["errorMessage"]
    assert agent_store._agents == {}


def test_admin_agent_upsert_rejects_unbound_mcp_allow_rule(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/invalid_mcp_policy",
            json={
                "node_class": "chat",
                "mcp": ["filesystem"],
                "tool_policy": {"mode": "allowlist", "allowed": ["mcp.remote.*"]},
            },
        )

    assert response.json()["success"] is False
    assert "mcp.remote.*" in response.json()["errorMessage"]
    assert agent_store._agents == {}


def test_admin_agent_policy_preserves_known_runtime_deny_categories(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    denied = [
        "bash_tools.*",
        "bi_tools.delete_dashboard",
        "orchestrator_tools.*",
        "scheduler_tools.delete_job",
        "skill_authoring_tools.*",
        "skills.*",
        "sub_agent_tools.task",
        "web_tool.web_fetch",
        "mcp.retired-server.*",
    ]
    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/defensive_denies",
            json={
                "node_class": "chat",
                "tool_policy": {"mode": "inherit", "denied": denied},
            },
        )

    assert response.json()["success"] is True
    assert response.json()["data"]["tool_policy"]["denied"] == sorted(denied)


def test_visual_agent_policy_rejects_other_artifact_type_method(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/visual_report_policy",
            json={
                "node_class": "gen_visual_report",
                "tool_policy": {
                    "mode": "allowlist",
                    "allowed": ["artifact_tools.start_new_dashboard"],
                },
            },
        )

    assert response.json()["success"] is False
    assert "artifact_tools.start_new_dashboard" in response.json()["errorMessage"]
    assert agent_store._agents == {}


def test_admin_agent_upsert_rejects_mcp_for_unsupported_node_class(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        response = client.put(
            "/api/v1/admin/agents/report_writer",
            json={"node_class": "gen_report", "mcp": ["filesystem"]},
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "does not support MCP" in response.json()["errorMessage"]
    assert agent_store._agents == {}


def test_admin_agent_upsert_accepts_visual_artifact_node_classes(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        report_response = client.put(
            "/api/v1/admin/agents/visual_report_writer",
            json={"name": "Visual Report Writer", "node_class": "gen_visual_report"},
        )
        dashboard_response = client.put(
            "/api/v1/admin/agents/visual_dashboard_writer",
            json={"name": "Visual Dashboard Writer", "node_class": "gen_visual_dashboard"},
        )

    assert report_response.json()["success"] is True
    assert report_response.json()["data"]["node_class"] == "gen_visual_report"
    assert dashboard_response.json()["success"] is True
    assert dashboard_response.json()["data"]["node_class"] == "gen_visual_dashboard"


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
        "mcp": ["filesystem"],
        "scoped_context": {
            "_enterprise_agent_policy": {
                "tool_policy": {"mode": "allowlist", "allowed": ["db_tools.read_query"]},
                "runtime_policy": {},
            }
        },
        "acl": {"visibility": "enterprise"},
    }

    materialize_enterprise_agent(agent_config, record)

    assert "sales_sql" in agent_config.agentic_nodes
    entry = agent_config.agentic_nodes["sales_sql"]
    assert entry["id"] == "sales_sql"
    assert entry["node_class"] == "gen_sql"
    assert entry["tools"] == "db_tools.read_query"
    assert entry["mcp"] == "filesystem"
    assert entry["tool_policy"]["allowed"] == ["db_tools.read_query", "mcp.filesystem.*"]


def test_enterprise_agent_materializes_custom_prompt_content():
    agent_config = SimpleNamespace(agentic_nodes={})
    record = {
        "agent_id": "chat_custom",
        "node_class": "chat",
        "status": "published",
        "prompt_template": "You are the custom chat Agent.",
        "prompt_version": "1.0",
        "tools": [],
        "mcp": [],
        "scoped_context": {},
        "acl": {"visibility": "enterprise"},
    }

    materialize_enterprise_agent(agent_config, record)

    entry = agent_config.agentic_nodes["chat_custom"]
    assert entry["system_prompt"] == "chat_custom"
    assert entry["prompt_template"] == "You are the custom chat Agent."
    assert entry["prompt_version"] == "1.0"


def test_enterprise_agent_without_custom_prompt_uses_latest_builtin_template():
    agent_config = SimpleNamespace(agentic_nodes={})
    record = {
        "agent_id": "chat_custom",
        "node_class": "chat",
        "status": "published",
        "prompt_template": None,
        "prompt_version": "1.0",
        "tools": [],
        "mcp": [],
        "scoped_context": {},
        "acl": {"visibility": "enterprise"},
    }

    materialize_enterprise_agent(agent_config, record)

    entry = agent_config.agentic_nodes["chat_custom"]
    assert entry["system_prompt"] == "chat"
    assert entry["prompt_template"] is None
    assert entry["prompt_version"] is None


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


def test_admin_can_publish_builtin_with_acl_and_tool_policy_overlay(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store, enabled=True)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        status_response = client.put("/api/v1/admin/agents/gen_sql/status", json={"status": "published"})
        acl_response = client.put(
            "/api/v1/admin/agents/gen_sql/acl",
            json={"visibility": "enterprise", "allowed_roles": [], "allowed_user_ids": []},
        )
        policy_response = client.put(
            "/api/v1/admin/agents/gen_sql/policy",
            json={
                "tool_policy": {
                    "mode": "allowlist",
                    "allowed": ["db_tools.list_tables", "db_tools.describe_table"],
                    "denied": ["filesystem_tools.*", "bash_tools.*"],
                },
                "runtime_policy": {
                    "allow_subagent_delegation": False,
                    "allowed_subagents": [],
                },
            },
        )

    assert status_response.json()["success"] is True
    assert acl_response.json()["data"]["visibility"] == "enterprise"
    assert policy_response.json()["data"]["tool_policy"]["mode"] == "allowlist"
    assert "max_permission_mode" not in policy_response.json()["data"]["runtime_policy"]
    assert agent_store._agents["gen_sql"]["scoped_context"]["_enterprise_agent_policy"]["tool_policy"]["denied"] == [
        "bash_tools.*",
        "filesystem_tools.*",
    ]

    ordinary_ctx = AppContext(user_id="alice", permissions=set())
    with _client(ordinary_ctx) as client:
        list_response = client.get("/api/v1/agents")
        detail_response = client.get("/api/v1/agents/gen_sql")

    assert "gen_sql" in {item["agent_id"] for item in list_response.json()["data"]}
    assert detail_response.json()["data"]["tool_policy"]["allowed"] == [
        "db_tools.describe_table",
        "db_tools.list_tables",
    ]


def test_admin_policy_update_rejects_unknown_pattern_without_persisting(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store, enabled=True)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        client.put("/api/v1/admin/agents/gen_sql/status", json={"status": "published"})
        before = dict(agent_store._agents["gen_sql"])
        response = client.put(
            "/api/v1/admin/agents/gen_sql/policy",
            json={
                "tool_policy": {"mode": "allowlist", "allowed": ["unknown_tools.*"]},
                "runtime_policy": {"allow_subagent_delegation": False},
            },
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "AGENT_POLICY_INVALID"
    assert agent_store._agents["gen_sql"] == before


def test_disabled_agent_can_clear_but_not_assign_default_users(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    extensions = _install_extensions(monkeypatch, agent_store, enabled=True)
    extensions.user_store._users["alice"] = {"user_id": "alice", "enabled": True}
    asyncio.run(extensions.user_store.put_chat_preference(user_id="alice", default_agent_id="chat"))
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        disable_response = client.put("/api/v1/admin/agents/chat/status", json={"status": "disabled"})
        clear_response = client.put(
            "/api/v1/admin/agents/chat/default-users",
            json={"user_ids": []},
        )
        assign_response = client.put(
            "/api/v1/admin/agents/chat/default-users",
            json={"user_ids": ["alice"]},
        )

    assert disable_response.json()["data"]["status"] == "disabled"
    assert clear_response.json()["success"] is True
    assert clear_response.json()["data"] == []
    assert assign_response.json()["errorCode"] == "AGENT_DEFAULT_REQUIRES_PUBLISHED"
    preference = asyncio.run(extensions.user_store.get_chat_preference("alice"))
    assert preference["default_agent_id"] is None


def test_effective_default_priority_user_enterprise_then_first_available(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    extensions = _install_extensions(monkeypatch, agent_store, enabled=True)
    extensions.user_store._users["alice"] = {"user_id": "alice", "enabled": True}
    agent_store._agents["safe_chat"] = {
        "agent_id": "safe_chat",
        "name": "Safe Chat",
        "node_class": "chat",
        "status": "published",
        "acl": {"visibility": "enterprise"},
    }
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})
    with _client(admin_ctx) as client:
        enterprise_response = client.put(
            "/api/v1/admin/agents/default",
            json={"default_agent_id": "safe_chat"},
        )
        default_users_response = client.put(
            "/api/v1/admin/agents/chat/default-users",
            json={"user_ids": ["alice"]},
        )

    assert enterprise_response.json()["data"]["default_agent_id"] == "safe_chat"
    assert default_users_response.json()["data"] == ["alice"]

    alice_ctx = AppContext(user_id="alice", permissions=set())
    with _client(alice_ctx) as client:
        personal_response = client.get("/api/v1/me/agent-preferences")
        client.put("/api/v1/me/agent-preferences", json={"default_agent_id": None})
        enterprise_fallback = client.get("/api/v1/me/agent-preferences")

    assert personal_response.json()["data"]["default_agent_id"] == "chat"
    assert personal_response.json()["data"]["source"] == "user"
    assert enterprise_fallback.json()["data"]["default_agent_id"] == "safe_chat"
    assert enterprise_fallback.json()["data"]["source"] == "enterprise"

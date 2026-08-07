import argparse
import asyncio
import json
from pathlib import Path
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
from datus.api.enterprise.prompt_versions import prompt_content_sha256
from datus.api.service import create_app
from datus.utils.path_manager import DatusPathManager
from datus_enterprise.agent_registry import (
    ENTERPRISE_AGENT_NODE_CAPABILITIES,
    ENTERPRISE_AGENT_NODE_CLASSES,
    ENTERPRISE_BUILTIN_AGENT_IDS,
    materialize_enterprise_agent,
    validate_agent_id,
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


def _client(ctx: AppContext, *, agent_config=None):
    app = FastAPI()
    app.include_router(agent_routes.router)

    service_agent_config = agent_config or SimpleNamespace(
        path_manager=DatusPathManager(
            datus_home=Path(__file__).parent / "__missing_datus_home__",
        )
    )

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace(agent_config=service_agent_config)

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
        "explore",
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
    assert items["explore"]["source"] == "builtin"
    assert items["explore"]["node_class"] == "explore"
    assert items["explore"]["status"] == "disabled"
    assert items["explore"]["acl"]["visibility"] == "private"
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


def test_explore_is_reserved_and_has_readonly_enterprise_tool_reference(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents/tool-reference", params={"node_class": "explore"})

    assert "explore" in ENTERPRISE_BUILTIN_AGENT_IDS
    assert validate_agent_id("explore") is not None
    assert response.status_code == 200
    assert response.json()["success"] is True
    data = response.json()["data"]
    assert data["default_tools"] == [
        "db_tools.*",
        "context_search_tools.*",
        "date_parsing_tools.*",
        "filesystem_tools.read_file",
        "filesystem_tools.glob",
        "filesystem_tools.grep",
    ]
    assert data["tool_types"]["filesystem_tools"]["tools"] == ["read_file", "glob", "grep"]


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


def test_admin_builtin_agent_detail_uses_running_service_template_home(monkeypatch, tmp_path):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})
    default_home = tmp_path / "default-user"
    stale_template_dir = default_home / ".datus" / "template"
    stale_template_dir.mkdir(parents=True)
    (stale_template_dir / "chat_system_1.2.j2").write_text(
        "STALE DEFAULT HOME PROMPT",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(default_home))

    runtime_home = tmp_path / "runtime-home"
    agent_config = SimpleNamespace(path_manager=DatusPathManager(datus_home=runtime_home))

    with _client(ctx, agent_config=agent_config) as client:
        response = client.get("/api/v1/admin/agents/chat")

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["prompt_source"] == "builtin"
    assert "STALE DEFAULT HOME PROMPT" not in detail["prompt_template"]
    assert "{% if has_ask_user_tool %}" in detail["prompt_template"]
    assert "reference SQL and external knowledge" not in detail["prompt_template"]


def test_admin_agent_fallback_uses_running_service_user_override(monkeypatch, tmp_path):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    agent_store._agents["sales_chat"] = {
        "agent_id": "sales_chat",
        "name": "Sales Chat",
        "node_class": "chat",
        "status": "published",
        "prompt_template": None,
        "prompt_version": "1.0",
        "acl": {"visibility": "enterprise"},
    }
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    default_home = tmp_path / "default-user"
    stale_template_dir = default_home / ".datus" / "template"
    stale_template_dir.mkdir(parents=True)
    (stale_template_dir / "chat_system_1.2.j2").write_text(
        "STALE DEFAULT HOME PROMPT",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(default_home))

    runtime_home = tmp_path / "runtime-home"
    runtime_template_dir = runtime_home / "template"
    runtime_template_dir.mkdir(parents=True)
    runtime_prompt = "RUNTIME HOME USER OVERRIDE"
    (runtime_template_dir / "chat_system_1.2.j2").write_text(runtime_prompt, encoding="utf-8")
    agent_config = SimpleNamespace(path_manager=DatusPathManager(datus_home=runtime_home))

    with _client(ctx, agent_config=agent_config) as client:
        response = client.get("/api/v1/admin/agents/sales_chat")

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["prompt_source"] == "user_override_fallback"
    assert detail["prompt_template_content"] == runtime_prompt
    assert detail["prompt_revision"] == prompt_content_sha256(runtime_prompt)


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
                "tools": ["db_tools.execute_sql"],
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


def test_admin_agent_prompt_versions_create_preview_activate_and_conflict(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, agent_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        create_agent_response = client.put(
            "/api/v1/admin/agents/versioned_sql",
            json={
                "name": "Versioned SQL",
                "node_class": "gen_sql",
                "prompt_template": "Prompt body v1",
                "prompt_version": "1.0",
            },
        )
        list_response = client.get("/api/v1/admin/agents/versioned_sql/prompt-versions")
        active_v1 = list_response.json()["data"]["active_version_id"]
        create_version_response = client.post(
            "/api/v1/admin/agents/versioned_sql/prompt-versions",
            json={
                "version": "2.0",
                "prompt_template": "Prompt body v2 secret marker",
                "change_note": "Tighten query constraints",
                "based_on_version_id": active_v1,
            },
        )
        version_v2 = create_version_response.json()["data"]["version_id"]
        preview_response = client.get(f"/api/v1/admin/agents/versioned_sql/prompt-versions/{version_v2}")
        activate_response = client.put(
            "/api/v1/admin/agents/versioned_sql/prompt-version",
            json={"version_id": version_v2, "expected_active_version_id": active_v1},
        )
        detail_response = client.get("/api/v1/admin/agents/versioned_sql")
        stale_activation_response = client.put(
            "/api/v1/admin/agents/versioned_sql/prompt-version",
            json={"version_id": active_v1, "expected_active_version_id": active_v1},
        )

    assert create_agent_response.status_code == 200
    assert list_response.status_code == 200
    versions = list_response.json()["data"]["versions"]
    assert len(versions) == 1
    assert "prompt_template" not in versions[0]
    assert versions[0]["version"] == "1.0"
    assert versions[0]["active"] is True
    assert create_version_response.status_code == 200
    assert create_version_response.json()["data"]["active"] is False
    assert preview_response.json()["data"]["prompt_template"] == "Prompt body v2 secret marker"
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["active"] is True
    detail = detail_response.json()["data"]
    assert detail["prompt_version"] == "2.0"
    assert detail["resolved_prompt_version"] == "2.0"
    assert detail["prompt_source"] == "enterprise"
    assert detail["active_prompt_version_id"] == version_v2
    assert detail["prompt_revision"] == activate_response.json()["data"]["content_sha256"]
    assert stale_activation_response.status_code == 409
    assert stale_activation_response.json()["detail"] == "AGENT_PROMPT_VERSION_CONFLICT"
    assert "Prompt body v2 secret marker" not in repr([event.metadata for event in audit_sink.events])


def test_admin_agent_prompt_version_legacy_read_is_side_effect_free_and_migrates_on_write(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["legacy_sql"] = {
        "agent_id": "legacy_sql",
        "name": "Legacy SQL",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": "Legacy prompt body",
        "prompt_version": "1.7",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        list_response = client.get("/api/v1/admin/agents/legacy_sql/prompt-versions")
        legacy = list_response.json()["data"]["versions"][0]
        assert agent_store._prompt_versions == {}
        create_response = client.post(
            "/api/v1/admin/agents/legacy_sql/prompt-versions",
            json={
                "version": "2.0",
                "prompt_template": "New prompt body",
                "based_on_version_id": legacy["version_id"],
            },
        )
        migrated_list_response = client.get("/api/v1/admin/agents/legacy_sql/prompt-versions")

    assert list_response.status_code == 200
    assert legacy["version"] == "1.7"
    assert legacy["version_id"].startswith("legacy_")
    assert create_response.status_code == 200
    assert create_response.json()["data"]["based_on_version_id"] != legacy["version_id"]
    migrated_versions = migrated_list_response.json()["data"]["versions"]
    assert {version["version"] for version in migrated_versions} == {"1.7", "2.0"}
    assert sum(1 for version in migrated_versions if version["active"]) == 1


def test_admin_agent_prompt_version_preserves_exact_prompt_whitespace(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})
    prompt_body = "\n  Keep this indentation exactly.\n"

    with _client(ctx) as client:
        create_response = client.put(
            "/api/v1/admin/agents/exact_prompt",
            json={
                "node_class": "gen_sql",
                "prompt_template": prompt_body,
                "prompt_version": "1.0",
            },
        )
        versions_response = client.get("/api/v1/admin/agents/exact_prompt/prompt-versions")
        unchanged_upsert_response = client.put(
            "/api/v1/admin/agents/exact_prompt",
            json={
                "node_class": "gen_sql",
                "description": "Metadata-only update",
                "prompt_template": prompt_body,
                "prompt_version": "1.0",
            },
        )

    expected_revision = prompt_content_sha256(prompt_body)
    assert create_response.json()["data"]["prompt_template"] == prompt_body
    assert create_response.json()["data"]["prompt_revision"] == expected_revision
    assert versions_response.json()["data"]["versions"][0]["content_sha256"] == expected_revision
    assert unchanged_upsert_response.status_code == 200
    assert unchanged_upsert_response.json()["success"] is True
    assert unchanged_upsert_response.json()["data"]["prompt_template"] == prompt_body


def test_legacy_prompt_identity_changes_with_version_or_language(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["legacy_identity"] = {
        "agent_id": "legacy_identity",
        "name": "Legacy identity",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": "Legacy prompt body",
        "prompt_version": "1.0",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        first_list = client.get("/api/v1/admin/agents/legacy_identity/prompt-versions")
        stale_legacy_id = first_list.json()["data"]["active_version_id"]
        agent_store._agents["legacy_identity"]["prompt_language"] = "zh-CN"
        second_list = client.get("/api/v1/admin/agents/legacy_identity/prompt-versions")
        create_response = client.post(
            "/api/v1/admin/agents/legacy_identity/prompt-versions",
            json={
                "version": "2.0",
                "prompt_template": "Prompt v2",
                "based_on_version_id": stale_legacy_id,
            },
        )

    assert second_list.json()["data"]["active_version_id"] != stale_legacy_id
    assert create_response.status_code == 404
    assert create_response.json()["detail"] == "RESOURCE_NOT_FOUND"


def test_admin_agent_prompt_version_is_scoped_to_agent_and_builtin_is_immutable(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        for agent_id in ("agent_a", "agent_b"):
            client.put(
                f"/api/v1/admin/agents/{agent_id}",
                json={
                    "node_class": "gen_sql",
                    "prompt_template": f"Prompt for {agent_id}",
                    "prompt_version": "1.0",
                },
            )
        versions_a = client.get("/api/v1/admin/agents/agent_a/prompt-versions").json()["data"]
        version_a = versions_a["active_version_id"]
        versions_b = client.get("/api/v1/admin/agents/agent_b/prompt-versions").json()["data"]
        cross_agent_detail = client.get(f"/api/v1/admin/agents/agent_b/prompt-versions/{version_a}")
        cross_agent_activation = client.put(
            "/api/v1/admin/agents/agent_b/prompt-version",
            json={
                "version_id": version_a,
                "expected_active_version_id": versions_b["active_version_id"],
            },
        )
        builtin_create = client.post(
            "/api/v1/admin/agents/gen_sql/prompt-versions",
            json={"version": "9.9", "prompt_template": "Override builtin"},
        )

    assert cross_agent_detail.status_code == 404
    assert cross_agent_activation.status_code == 404
    assert builtin_create.status_code == 409
    assert builtin_create.json()["detail"] == "AGENT_BUILTIN_IMMUTABLE"


def test_admin_agent_prompt_version_routes_require_admin_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseAgentStore())
    ctx = AppContext(user_id="operator", permissions={"module.chat"})

    with _client(ctx) as client:
        responses = [
            client.get("/api/v1/admin/agents/analyst/prompt-versions"),
            client.get("/api/v1/admin/agents/analyst/prompt-versions/version-1"),
            client.post(
                "/api/v1/admin/agents/analyst/prompt-versions",
                json={"version": "2.0", "prompt_template": "Prompt v2"},
            ),
            client.put(
                "/api/v1/admin/agents/analyst/prompt-version",
                json={"version_id": "version-1", "expected_active_version_id": None},
            ),
        ]

    assert all(response.status_code == 403 for response in responses)
    assert all("module.admin.agents" in response.json()["detail"] for response in responses)


def test_admin_agent_prompt_version_reads_are_side_effect_free_in_readonly(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["readonly_sql"] = {
        "agent_id": "readonly_sql",
        "name": "Readonly SQL",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": "Legacy readonly prompt",
        "prompt_version": "1.0",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, agent_store, enabled=True)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        list_response = client.get("/api/v1/admin/agents/readonly_sql/prompt-versions")
        legacy_version_id = list_response.json()["data"]["active_version_id"]
        detail_response = client.get(
            f"/api/v1/admin/agents/readonly_sql/prompt-versions/{legacy_version_id}",
        )
        create_response = client.post(
            "/api/v1/admin/agents/readonly_sql/prompt-versions",
            json={"version": "2.0", "prompt_template": "Prompt v2"},
        )
        activate_response = client.put(
            "/api/v1/admin/agents/readonly_sql/prompt-version",
            json={"version_id": legacy_version_id, "expected_active_version_id": legacy_version_id},
        )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert agent_store._prompt_versions == {}
    assert agent_store._active_prompt_versions == {}
    assert create_response.status_code == 403
    assert activate_response.status_code == 403
    assert create_response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    assert activate_response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"


def test_admin_agent_detail_reports_builtin_prompt_fallback_provenance(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["fallback_sql"] = {
        "agent_id": "fallback_sql",
        "name": "Fallback SQL",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": None,
        "prompt_version": "9.0-configured",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/agents/fallback_sql")

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["prompt_source"] == "builtin_fallback"
    assert detail["prompt_template"] is None
    assert detail["prompt_template_content"]
    assert detail["configured_prompt_version"] == "9.0-configured"
    assert detail["resolved_prompt_version"] != detail["configured_prompt_version"]
    assert len(detail["prompt_revision"]) == 64
    assert detail["active_prompt_version_id"] is None


def test_admin_agent_prompt_version_duplicate_activate_and_validation(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        client.put(
            "/api/v1/admin/agents/version_rules",
            json={
                "node_class": "gen_sql",
                "prompt_template": "Prompt v1",
                "prompt_version": "1.0",
            },
        )
        duplicate_response = client.post(
            "/api/v1/admin/agents/version_rules/prompt-versions",
            json={"version": "1.0", "prompt_template": "Another prompt"},
        )
        activate_create_response = client.post(
            "/api/v1/admin/agents/version_rules/prompt-versions",
            json={
                "version": "2.0",
                "prompt_template": "Prompt v2",
                "activate": True,
            },
        )
        empty_prompt_response = client.post(
            "/api/v1/admin/agents/version_rules/prompt-versions",
            json={"version": "3.0", "prompt_template": "   "},
        )
        long_version_response = client.post(
            "/api/v1/admin/agents/version_rules/prompt-versions",
            json={"version": "v" * 41, "prompt_template": "Prompt v3"},
        )
        detail_response = client.get("/api/v1/admin/agents/version_rules")

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "AGENT_PROMPT_VERSION_CONFLICT"
    assert activate_create_response.status_code == 200
    assert activate_create_response.json()["data"]["active"] is True
    assert detail_response.json()["data"]["prompt_version"] == "2.0"
    assert empty_prompt_response.status_code == 422
    assert empty_prompt_response.json()["detail"] == "AGENT_PROMPT_VERSION_INVALID"
    assert long_version_response.status_code == 422


def test_admin_agent_legacy_migration_rejects_conflicting_version_label(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    agent_store._agents["legacy_conflict"] = {
        "agent_id": "legacy_conflict",
        "name": "Legacy conflict",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": "Legacy body",
        "prompt_version": "1.0",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    asyncio.run(
        agent_store.create_prompt_version(
            agent_id="legacy_conflict",
            version="1.0",
            prompt_template="Different stored body",
            prompt_language="en",
            change_note=None,
            based_on_version_id=None,
            created_by="operator",
        ),
    )
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        response = client.post(
            "/api/v1/admin/agents/legacy_conflict/prompt-versions",
            json={"version": "2.0", "prompt_template": "Prompt v2"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "AGENT_PROMPT_VERSION_CONFLICT"


def test_admin_agent_prompt_version_store_failures_are_stable_and_audited(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    audit_sink = CollectingAuditSink()
    agent_store._agents["store_failure"] = {
        "agent_id": "store_failure",
        "name": "Store failure",
        "node_class": "gen_sql",
        "status": "draft",
        "prompt_template": None,
        "prompt_version": "1.0",
        "prompt_language": "en",
        "acl": {"visibility": "enterprise"},
    }
    original_get_prompt_version = agent_store.get_prompt_version
    original_create_prompt_version = agent_store.create_prompt_version

    async def fail_read(_agent_id, _version_id):
        raise RuntimeError("database secret detail")

    async def fail_create(**_kwargs):
        raise RuntimeError("database secret detail")

    monkeypatch.setattr(agent_store, "get_prompt_version", fail_read)
    monkeypatch.setattr(agent_store, "create_prompt_version", fail_create)
    _install_extensions(monkeypatch, agent_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        read_response = client.get("/api/v1/admin/agents/store_failure/prompt-versions/missing")
        create_response = client.post(
            "/api/v1/admin/agents/store_failure/prompt-versions",
            json={"version": "2.0", "prompt_template": "Prompt v2"},
        )

    assert read_response.status_code == 200
    assert read_response.json()["errorCode"] == "AGENT_PROMPT_VERSION_READ_FAILED"
    assert create_response.status_code == 200
    assert create_response.json()["errorCode"] == "AGENT_PROMPT_VERSION_CREATE_FAILED"
    assert "database secret detail" not in str(read_response.json())
    assert "database secret detail" not in str(create_response.json())
    assert audit_sink.events[-1].decision == "deny"

    monkeypatch.setattr(agent_store, "get_prompt_version", original_get_prompt_version)
    monkeypatch.setattr(agent_store, "create_prompt_version", original_create_prompt_version)


def test_admin_agent_upsert_requires_new_version_for_prompt_changes(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        client.put(
            "/api/v1/admin/agents/immutable_sql",
            json={
                "node_class": "gen_sql",
                "prompt_template": "Original prompt",
                "prompt_version": "1.0",
            },
        )
        conflict_response = client.put(
            "/api/v1/admin/agents/immutable_sql",
            json={
                "node_class": "gen_sql",
                "prompt_template": "Overwritten prompt",
                "prompt_version": "1.0",
            },
        )
        detail_response = client.get("/api/v1/admin/agents/immutable_sql")

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "AGENT_PROMPT_VERSION_REQUIRED"
    assert detail_response.json()["data"]["prompt_template"] == "Original prompt"


def test_admin_agent_upsert_cannot_bypass_unactivated_prompt_history(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(ctx) as client:
        client.put(
            "/api/v1/admin/agents/fallback_history",
            json={"node_class": "gen_sql"},
        )
        create_version_response = client.post(
            "/api/v1/admin/agents/fallback_history/prompt-versions",
            json={"version": "1.0-custom", "prompt_template": "Unactivated custom prompt"},
        )
        bypass_response = client.put(
            "/api/v1/admin/agents/fallback_history",
            json={
                "node_class": "gen_sql",
                "prompt_template": "Bypass prompt",
                "prompt_version": "2.0",
            },
        )
        detail_response = client.get("/api/v1/admin/agents/fallback_history")

    assert create_version_response.status_code == 200
    assert create_version_response.json()["data"]["active"] is False
    assert bypass_response.status_code == 409
    assert bypass_response.json()["detail"] == "AGENT_PROMPT_VERSION_REQUIRED"
    assert detail_response.json()["data"]["prompt_template"] is None
    assert detail_response.json()["data"]["prompt_source"] == "builtin_fallback"


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


def test_admin_agent_upsert_accepts_custom_chat_node_class(monkeypatch, tmp_path):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    config_path = tmp_path / "conf" / ".mcp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({"mcpServers": {"filesystem": {"type": "http", "url": "https://mcp.example.com"}}}),
        encoding="utf-8",
    )
    agent_config = SimpleNamespace(path_manager=DatusPathManager(datus_home=tmp_path))

    with _client(admin_ctx, agent_config=agent_config) as client:
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


def test_published_explore_builtin_is_available_only_through_its_acl(monkeypatch):
    agent_store = InMemoryEnterpriseAgentStore()
    _install_extensions(monkeypatch, agent_store, enabled=True)
    admin_ctx = AppContext(user_id="operator", permissions={"module.admin.agents"})

    with _client(admin_ctx) as client:
        status_response = client.put("/api/v1/admin/agents/explore/status", json={"status": "published"})
        acl_response = client.put(
            "/api/v1/admin/agents/explore/acl",
            json={"visibility": "role", "allowed_roles": ["analyst"], "allowed_user_ids": []},
        )

    assert status_response.json()["success"] is True
    assert acl_response.json()["success"] is True

    allowed_ctx = AppContext(user_id="alice", roles=["analyst"], permissions=set())
    denied_ctx = AppContext(user_id="bob", roles=["viewer"], permissions={"module.sql_executor"})
    with _client(allowed_ctx) as client:
        allowed_response = client.get("/api/v1/agents")
        tools_response = client.get("/api/v1/agents/explore/tools")
    with _client(denied_ctx) as client:
        denied_response = client.get("/api/v1/agents")

    assert "explore" in {item["agent_id"] for item in allowed_response.json()["data"]}
    assert tools_response.json()["success"] is True
    assert "filesystem_tools.write_file" not in tools_response.json()["data"]["default_tools"]
    assert "explore" not in {item["agent_id"] for item in denied_response.json()["data"]}


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

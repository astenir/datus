"""Pydantic request and response models for enterprise Agent APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentAcl(BaseModel):
    """Enterprise agent ACL."""

    visibility: str = Field(default="private", description="private / role / enterprise")
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class AgentToolPolicy(BaseModel):
    """Server-enforced LLM tool exposure and invocation policy."""

    mode: str = Field(default="inherit", description="inherit / allowlist")
    allowed: list[str] = Field(default_factory=list, max_length=300)
    denied: list[str] = Field(default_factory=list, max_length=300)


class AgentRuntimePolicy(BaseModel):
    """Server-enforced Agent delegation policy."""

    allow_subagent_delegation: bool = False
    allowed_subagents: list[str] = Field(default_factory=list, max_length=100)


class AgentPolicy(BaseModel):
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)


class UpsertEnterpriseAgentRequest(BaseModel):
    """Enterprise custom agent definition mutation."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    node_class: str = Field(default="gen_sql")
    status: str = Field(default="draft")
    datasource_id: str | None = Field(default=None, max_length=128)
    artifact_slug: str | None = Field(default=None, max_length=80)
    prompt_template: str | None = None
    prompt_language: str = Field(default="en", max_length=20)
    prompt_version: str | None = Field(default="1.0", max_length=40)
    tools: list[str] = Field(default_factory=list, max_length=200)
    mcp: list[str] = Field(default_factory=list, max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=200)
    scoped_context: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list, max_length=100)
    max_turns: int = Field(default=30, ge=1, le=200)
    acl: AgentAcl = Field(default_factory=AgentAcl)
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)


class SetAgentStatusRequest(BaseModel):
    """Enterprise agent status mutation."""

    status: str


class EnterpriseAgentSummary(BaseModel):
    """Sanitized enterprise agent summary."""

    agent_id: str
    name: str
    description: str | None = None
    node_class: str
    status: str
    source: str = "enterprise"
    owner_user_id: str | None = None
    datasource_id: str | None = None
    artifact_slug: str | None = None
    acl: AgentAcl | None = None
    tool_policy: AgentToolPolicy = Field(default_factory=AgentToolPolicy)
    runtime_policy: AgentRuntimePolicy = Field(default_factory=AgentRuntimePolicy)
    enterprise_default: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class EnterpriseAgentDetail(EnterpriseAgentSummary):
    """Sanitized enterprise agent detail."""

    prompt_template: str | None = None
    prompt_template_name: str | None = None
    prompt_template_content: str | None = None
    prompt_language: str = "en"
    prompt_version: str | None = "1.0"
    prompt_source: str = "enterprise"
    configured_prompt_version: str | None = None
    resolved_prompt_version: str | None = None
    prompt_revision: str | None = None
    active_prompt_version_id: str | None = None
    tools: list[str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    scoped_context: dict[str, Any] = Field(default_factory=dict)
    rules: list[str] = Field(default_factory=list)
    max_turns: int = 30


class AgentPromptVersionSummary(BaseModel):
    """Immutable prompt version provenance without the prompt body."""

    version_id: str
    version: str
    content_sha256: str
    change_note: str | None = None
    based_on_version_id: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    active: bool = False


class AgentPromptVersionDetail(AgentPromptVersionSummary):
    """Authorized prompt version detail including the prompt body."""

    prompt_template: str
    prompt_language: str = "en"


class AgentPromptVersionCollection(BaseModel):
    """Prompt version history and current active reference for one Agent."""

    active_version_id: str | None = None
    versions: list[AgentPromptVersionSummary] = Field(default_factory=list)


class CreateAgentPromptVersionRequest(BaseModel):
    """Create one immutable prompt version."""

    version: str = Field(min_length=1, max_length=40)
    prompt_template: str = Field(min_length=1)
    prompt_language: str = Field(default="en", max_length=20)
    change_note: str | None = Field(default=None, max_length=500)
    based_on_version_id: str | None = Field(default=None, max_length=80)
    activate: bool = False


class ActivateAgentPromptVersionRequest(BaseModel):
    """Activate one prompt version with an optimistic concurrency check."""

    version_id: str = Field(min_length=1, max_length=80)
    expected_active_version_id: str | None


class EnterpriseAgentNodeType(BaseModel):
    """Supported enterprise Agent node type metadata."""

    node_class: str
    label: str
    description: str
    supports_mcp: bool = False


class AgentPreferenceSummary(BaseModel):
    """Current user's default Agent preference."""

    default_agent_id: str | None = None
    source: str = "none"
    user_default_agent_id: str | None = None
    enterprise_default_agent_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentAclUserSummary(BaseModel):
    """Sanitized enterprise user summary for Agent ACL selectors."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None


class AgentAclRoleSummary(BaseModel):
    """Sanitized enterprise role summary for Agent ACL selectors."""

    role_id: str
    name: str
    description: str | None = None


class UpdateAgentPreferenceRequest(BaseModel):
    """Current user's default Agent preference mutation."""

    default_agent_id: str | None = Field(default=None, max_length=80)


class UpdateDefaultUsersRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=500)

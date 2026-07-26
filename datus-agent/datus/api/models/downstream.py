"""Downstream-only API models kept outside upstream-owned model modules."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from datus.api.models.cli_models import (
    ExecuteSQLInput as UpstreamExecuteSQLInput,
)
from datus.api.models.cli_models import (
    FeedbackChatInput as UpstreamFeedbackChatInput,
)
from datus.api.models.cli_models import (
    StreamChatInput as UpstreamStreamChatInput,
)
from datus.api.models.config_models import ModelPricing
from datus.utils.time_utils import now_utc_iso


class ExecuteSQLInput(UpstreamExecuteSQLInput):
    """Input model for SQL execution."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "database_name": "sales_db",
                "datasource": "warehouse",
                "sql_query": "SELECT * FROM users WHERE status = 'active'",
                "result_format": "csv",
                "system": False,
                "execute_task_id": "caller-generated-task-id",
            }
        }
    )

    datasource: Optional[str] = Field(None, description="Datasource name")


class StreamChatInput(UpstreamStreamChatInput):
    """Input for streaming chat via /chat/stream."""

    model_credential_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description=(
            "Current user's model credential ID to use for this request. "
            "When set, the credential's configured provider and model take priority over model."
        ),
    )


class FeedbackChatInput(UpstreamFeedbackChatInput):
    """Input for /chat/feedback — reaction-triggered feedback agent.

    ``message`` is server-rendered from the reaction fields via
    :func:`datus.utils.feedback_prompt.build_reaction_feedback_prompt`, so callers
    can leave it empty.
    """

    model_credential_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description=(
            "Current user's model credential ID to use for this request. "
            "When set, the credential's configured provider and model take priority over model."
        ),
    )


class UserInteractionData(BaseModel):
    """Result for a submitted user interaction."""

    interaction_key: str = Field(..., description="Interaction key that was submitted")
    submitted: bool = Field(..., description="Whether the interaction answer was accepted")


class ChatSessionTerminalEvent(BaseModel):
    """Durable display-only outcome for one established chat run."""

    event_id: str = Field(..., description="Stable idempotency key for the terminal event")
    event_type: Literal["error", "cancelled", "timeout"] = Field(..., description="Terminal outcome type")
    error: str = Field(..., description="Terminal outcome detail for authorized session history readers")
    error_type: str = Field(..., description="Stable error or cancellation code")
    created_at: str = Field(default_factory=now_utc_iso, description="UTC event timestamp")


class ChatSessionSubagentEvent(BaseModel):
    """Durable display-only link from a parent task call to a child session."""

    event_id: str = Field(..., description="Stable idempotency key for the delegation event")
    event_type: Literal["subagent"] = Field(default="subagent", description="Display sidecar event type")
    parent_action_id: str = Field(..., description="Parent task function call id")
    child_session_id: str = Field(..., description="Persisted nested sub-agent session id")
    subagent_type: str = Field(..., description="Delegated sub-agent type")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Original task display arguments")
    created_at: str = Field(default_factory=now_utc_iso, description="UTC event timestamp")


class ModelInfo(BaseModel):
    """A single model entry returned by the catalog endpoint."""

    model_config = ConfigDict(exclude_none=True)

    provider: str = Field(..., description="Provider key from providers.yml, or 'custom' for agent.models entries")
    id: str = Field(..., description="Model slug as consumed by the SDK")
    model: Optional[str] = Field(
        None, description="Actual model name (same as id for provider models, ModelConfig.model for custom)"
    )
    name: Optional[str] = Field(None, description="Human-readable model name")
    capabilities: List[str] = Field(default_factory=lambda: ["chat"], description="Supported model capabilities")
    context_length: Optional[int] = Field(None, description="Maximum context window in tokens")
    max_tokens: Optional[int] = Field(None, description="Maximum completion tokens")
    pricing: Optional[ModelPricing] = Field(None, description="Per-token pricing, when available")


class ModelsData(BaseModel):
    """Response payload for GET /api/v1/models."""

    model_config = ConfigDict(exclude_none=True)

    models: List[ModelInfo] = Field(..., description="Flat list of available models")
    providers: List[str] = Field(..., description="Provider keys represented in this response")
    current_model: Optional[str] = Field(None, description="Currently active model as 'provider/model'")
    fetched_at: Optional[str] = Field(None, description="ISO-8601 timestamp of the OpenRouter cache")
    source: str = Field(..., description="Where the data came from: cache or catalog")


class AgentConfigSummaryData(BaseModel):
    """Frontend-facing summary of the loaded project agent configuration."""

    model_config = ConfigDict(exclude_none=True)

    target: Optional[Any] = Field(None, description="Active target model configuration or legacy target value")
    providers: Dict[str, Any] = Field(default_factory=dict, description="Configured shared provider credentials")
    provider_options: List[Dict[str, Any]] = Field(default_factory=list, description="Provider catalog options")
    models: Dict[str, Any] = Field(default_factory=dict, description="Configured legacy/self-hosted model entries")
    current_datasource: Optional[str] = Field(None, description="Currently active datasource key")
    datasources: Dict[str, Any] = Field(default_factory=dict, description="Configured datasource entries")
    home: str = Field(..., description="Resolved agent home/project storage path")


class MutationResultData(BaseModel):
    """Generic acknowledgement for configuration mutations."""

    updated: bool = Field(..., description="Whether the configuration was updated")


class ProbeResultData(BaseModel):
    """Connectivity probe result."""

    ok: bool = Field(..., description="Whether the probe succeeded")
    message: Optional[str] = Field(None, description="Failure detail when ok=false")


class SuccessStoryInput(BaseModel):
    """Canonical reference to a successful SQL execution in chat history."""

    session_id: str = Field(..., min_length=1, max_length=255, description="Session ID that produced the SQL")
    call_tool_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tool call ID of the completed execute_sql/read_query action",
    )
    session_link: Optional[str] = Field(
        None,
        max_length=2048,
        description=(
            "Optional UI link that reopens the session. It is stored only as provenance; "
            "the server does not use it to resolve the SQL."
        ),
    )

    @field_validator("session_id", "call_tool_id")
    @classmethod
    def _strip_required_identifiers(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("session_link")
    @classmethod
    def _strip_optional_link(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class SuccessStorySource(BaseModel):
    """Server-resolved, trusted source used by the CSV persistence service."""

    session_id: str
    call_tool_id: str
    question: str
    sql: str
    datasource_id: str
    subagent_name: str
    session_link: Optional[str] = None


class SuccessStoryData(BaseModel):
    """Data returned after a success story is persisted."""

    story_id: str = Field(..., description="Stable ID derived from the canonical source execution")
    created: bool = Field(..., description="Whether this request created a new CSV row")
    datasource_id: str = Field(..., description="Canonical datasource recovered from the SQL tool execution")
    subagent_name: str = Field(..., description="Canonical subagent directory name used for storage")
    storage_key: str = Field(..., description="Success-story path relative to the benchmark directory")
    session_id: str = Field(..., description="Echoed session ID")
    timestamp: str = Field(..., description="UTC timestamp associated with the persisted row")


class AgentSummary(BaseModel):
    """Summary item returned by the agent list endpoint."""

    id: str = Field(..., description="Agent id used by API requests")
    name: str = Field(..., description="Agent display name")
    type: str = Field(..., description="Agent type, e.g. builtin, gen_sql, gen_report")
    description: str = Field(default="", description="Short agent description")


class AgentListData(BaseModel):
    """Agent list data."""

    agents: List[AgentSummary] = Field(default_factory=list, description="Available agents")


class ToolCategoryData(BaseModel):
    """Tool methods available under one tool category."""

    tools: List[str] = Field(default_factory=list, description="Tool method names")


class AgentUseToolsData(BaseModel):
    """Tool selection contract for one agent type."""

    default_tools: List[str] = Field(default_factory=list, description="Preselected tool patterns")
    tool_types: Dict[str, ToolCategoryData] = Field(
        default_factory=dict,
        description="User-facing tool categories and selectable methods",
    )


class AgentToolsData(BaseModel):
    """Full tool catalog returned by GET /agent/tools."""

    tools: Dict[str, List[str]] = Field(default_factory=dict, description="All valid tool categories and methods")


class IAgentInfo(BaseModel):
    """Detailed agent information."""

    id: str = Field(..., description="Agent id used by API requests")
    name: str = Field(..., description="Agent name")
    type: str = Field(..., description="Agent type, e.g. builtin, gen_sql, gen_report")
    description: str = Field(default="", description="Agent description")
    config_yaml: Optional[str] = Field(None, description="Agent configuration YAML, when available")
    system_prompt: Optional[str] = Field(None, description="System prompt, when available")
    tools: List[str] = Field(default_factory=list, description="Available tools")
    catalogs: List[str] = Field(default_factory=list, description="Catalog access patterns")
    subjects: List[str] = Field(default_factory=list, description="Subject access patterns")
    rules: List[str] = Field(default_factory=list, description="Additional rules")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class GetAgentData(BaseModel):
    """Get agent result data."""

    agent: IAgentInfo


class AgentMutationData(BaseModel):
    """Result payload for create/edit/delete agent mutations."""

    id: str = Field(..., description="Agent id")
    name: str = Field(..., description="Agent name")


class ReportEditSession(BaseModel):
    """Ephemeral handle for editing one report through a locked subagent."""

    edit_session_id: str = Field(..., description="Opaque edit-session identifier.")
    subagent_id: str = Field(..., description="Subagent id to pass to /api/v1/chat/stream.")
    artifact_type: str = Field("report", description="Artifact type locked by this edit session.")
    artifact_slug: str = Field(..., description="Report slug locked by this edit session.")
    owner_user_id: Optional[str] = Field(None, description="User that created the edit session.")
    created_at: str = Field(..., description="UTC ISO timestamp when the edit session was created.")


class DashboardEditSession(BaseModel):
    """Ephemeral handle for editing one dashboard through a locked subagent."""

    edit_session_id: str = Field(..., description="Opaque edit-session identifier.")
    subagent_id: str = Field(..., description="Subagent id to pass to /api/v1/chat/stream.")
    artifact_type: str = Field("dashboard", description="Artifact type locked by this edit session.")
    artifact_slug: str = Field(..., description="Dashboard slug locked by this edit session.")
    owner_user_id: Optional[str] = Field(None, description="User that created the edit session.")
    created_at: str = Field(..., description="UTC ISO timestamp when the edit session was created.")


class DatasourceConnectionStatus(BaseModel):
    """Cached connection health for a configured datasource."""

    datasource_id: str = Field(..., description="Datasource configuration key")
    status: Literal["unknown", "connecting", "connected", "failed", "timeout"] = Field(
        ..., description="Last known connection status"
    )
    last_checked: Optional[str] = Field(None, description="Last status update timestamp")
    latency_ms: Optional[int] = Field(None, description="Last successful/failed check duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Last connection error, if any")
    cached: bool = Field(..., description="Whether this status came from the in-process status cache")


class DatasourceStatusData(BaseModel):
    """Datasource connection status list."""

    statuses: List[DatasourceConnectionStatus] = Field(..., description="Datasource connection statuses")


class DatasourcePrewarmData(BaseModel):
    """Result of enqueuing a datasource connection prewarm."""

    datasource_id: str = Field(..., description="Datasource scheduled for background prewarm")
    status: Literal["queued", "already_running"] = Field(..., description="Prewarm scheduling status")


class UpdateServerInput(BaseModel):
    """Input model for updating an existing MCP server."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"type": "stdio", "command": "python", "args": ["-m", "new_server"]}}
    )

    type: str = Field(..., description="Server type (stdio, sse, http)")
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: Optional[List[str]] = Field(None, description="Arguments for stdio servers")
    url: Optional[str] = Field(None, description="URL for sse/http servers")
    headers: Optional[Dict[str, str]] = Field(None, description="Headers for sse/http servers")
    timeout: Optional[float] = Field(None, description="Timeout for sse/http servers")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables for stdio servers")
    cwd: Optional[str] = Field(None, description="Working directory for stdio servers")

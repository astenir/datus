"""Data models for success-story persistence endpoints."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


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

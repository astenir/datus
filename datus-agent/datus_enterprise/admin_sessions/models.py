"""Response models for enterprise session administration."""

from __future__ import annotations

from pydantic import BaseModel


class AdminSessionSummary(BaseModel):
    """Bounded session metadata for admin views."""

    session_id: str
    owner_user_id: str | None = None
    status: str
    is_running: bool = False
    runtime_snapshot_available: bool
    created_at: str | None = None
    updated_at: str | None = None
    event_count: int | None
    exists_on_disk: bool | None = None


class AdminSessionDetail(AdminSessionSummary):
    """Detailed bounded session metadata for one session."""

    consumer_offset: int | None
    error: str | None

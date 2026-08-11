"""Request and response models for enterprise datasource administration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SetDefaultDatasourceRequest(BaseModel):
    """Project-level datasource default mutation."""

    name: str


class AdminDatasourceSummary(BaseModel):
    """Sanitized datasource summary for admin selection UIs."""

    name: str
    display_name: str | None = None
    type: str | None = None
    is_default: bool = False


class UpsertDatasourceGrantRequest(BaseModel):
    """Datasource grant metadata mutation."""

    effect: Any = "allow"
    scope: Any = Field(default_factory=dict)


class AdminDatasourceGrantSummary(BaseModel):
    """Sanitized datasource grant metadata."""

    subject_type: str
    subject_id: str
    datasource_key: str
    effect: str
    scope: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AdminDatasourceGrantSubjectSummary(BaseModel):
    """Minimal role/user identity exposed to datasource grant editors."""

    subject_type: Literal["user", "role"]
    subject_id: str
    display_name: str | None = None
    enabled: bool | None = None

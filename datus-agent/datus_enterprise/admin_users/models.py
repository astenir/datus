"""Request and response models for enterprise user administration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UpsertAdminUserRequest(BaseModel):
    """Enterprise user metadata mutation."""

    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    enabled: bool = True
    external_user_id: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    last_seen_at: str | None = Field(default=None, max_length=100)


class AdminUserRoleSummary(BaseModel):
    """Sanitized role summary embedded in admin user details."""

    role_id: str
    name: str | None = None
    permissions: list[str] = Field(default_factory=list)
    built_in: bool = False


class AdminUserDatasourceGrantSummary(BaseModel):
    """Sanitized datasource grant summary embedded in admin user details."""

    subject_type: str
    subject_id: str
    datasource_key: str
    effect: str
    scope: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserSummary(BaseModel):
    """Sanitized enterprise user metadata."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    enabled: bool
    external_user_id: str | None = None
    department: str | None = None
    title: str | None = None
    last_seen_at: str | None = None
    role_ids: list[str] = Field(default_factory=list)
    role_count: int = 0
    direct_datasource_grant_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserDetail(AdminUserSummary):
    """Detailed enterprise user metadata for one admin user profile."""

    roles: list[AdminUserRoleSummary] = Field(default_factory=list)
    effective_permissions: list[str] = Field(default_factory=list)
    direct_datasource_grants: list[AdminUserDatasourceGrantSummary] = Field(default_factory=list)
    role_datasource_grants: list[AdminUserDatasourceGrantSummary] = Field(default_factory=list)
    role_datasource_grant_count: int = 0
    effective_datasource_grant_count: int = 0

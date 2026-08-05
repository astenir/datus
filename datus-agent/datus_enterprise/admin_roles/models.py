"""Request and response models for enterprise role administration."""

from __future__ import annotations

from pydantic import BaseModel, Field

MAX_PERMISSION_KEYS = 200


class UpsertAdminRoleRequest(BaseModel):
    """Enterprise role metadata and permission mutation."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=MAX_PERMISSION_KEYS)


class SetRolePermissionsRequest(BaseModel):
    """Enterprise role permission-set mutation."""

    permissions: list[str] = Field(default_factory=list, max_length=MAX_PERMISSION_KEYS)


class SetUserRolesRequest(BaseModel):
    """Enterprise user-role membership mutation."""

    role_ids: list[str] = Field(default_factory=list, max_length=MAX_PERMISSION_KEYS)


class AdminRoleSummary(BaseModel):
    """Sanitized enterprise role metadata."""

    role_id: str
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    built_in: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserRolesSummary(BaseModel):
    """Sanitized enterprise user-role membership."""

    user_id: str
    role_ids: list[str] = Field(default_factory=list)

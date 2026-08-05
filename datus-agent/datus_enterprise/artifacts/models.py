"""Pydantic models and type aliases for enterprise Artifact APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from datus.schemas.artifact_manifest import ArtifactManifest

ShareArtifactType = Literal["report", "dashboard"]


class AdminArtifactSummary(BaseModel):
    """Admin artifact inventory item."""

    artifact_type: Literal["report", "dashboard"]
    manifest: ArtifactManifest


class ArtifactAcl(BaseModel):
    """Admin-managed ACL metadata for a report or dashboard artifact."""

    owner_user_id: str
    visibility: Literal["private", "role", "enterprise"]
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)
    datasources: list[str] = Field(default_factory=list)


class ArtifactShareUpdate(BaseModel):
    """Creator-managed sharing fields for a report or dashboard artifact."""

    visibility: Literal["private", "role", "enterprise"] = "private"
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class ArtifactShare(BaseModel):
    """Creator-visible ACL sharing state for one artifact."""

    owner_user_id: str
    visibility: Literal["private", "role", "enterprise"]
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)


class ArtifactShareUserSummary(BaseModel):
    """Sanitized user directory item for artifact sharing selectors."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None


class ArtifactShareRoleSummary(BaseModel):
    """Sanitized role directory item for artifact sharing selectors."""

    role_id: str
    name: str
    description: str | None = None
    built_in: bool = False


class ArtifactListItem(ArtifactManifest):
    """User-visible artifact list item with current-user UI capabilities."""

    owner_user_id: str | None = None
    owner_display_name: str | None = None
    can_manage_share: bool = False
    can_edit: bool = False

"""Shared bounded pagination helpers for enterprise admin list routes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from datus.api.models.base_models import Result

ADMIN_LIST_DEFAULT_LIMIT = 20
ADMIN_LIST_MAX_LIMIT = 100

ItemT = TypeVar("ItemT")


class AdminPagination(BaseModel):
    """Offset pagination metadata returned alongside an admin list."""

    limit: int = Field(ge=1, le=ADMIN_LIST_MAX_LIMIT)
    offset: int = Field(ge=0)
    has_more: bool


class AdminListResult(Result[list[ItemT]], Generic[ItemT]):
    """Backward-compatible admin list result with additive page metadata."""

    pagination: AdminPagination | None = None


def paginate_admin_records(
    records: Sequence[ItemT],
    *,
    limit: int,
    offset: int,
    records_are_offset: bool = False,
) -> AdminListResult[ItemT]:
    """Return at most ``limit`` records and report whether another page exists."""

    start = 0 if records_are_offset else offset
    candidates = records[start : start + limit + 1]
    return AdminListResult(
        success=True,
        data=list(candidates[:limit]),
        pagination=AdminPagination(
            limit=limit,
            offset=offset,
            has_more=len(candidates) > limit,
        ),
    )

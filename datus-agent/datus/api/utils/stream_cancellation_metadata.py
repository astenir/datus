"""Downstream ownership checks for SSE cancellation tokens."""

import asyncio
from dataclasses import dataclass

from datus.api.utils import stream_cancellation as _base


@dataclass(frozen=True)
class CancelTokenMetadata:
    owner_user_id: str | None = None
    project_id: str | None = None


cancel_token_metadata: dict[str, CancelTokenMetadata] = {}


def _normalize_identity(value: str | None) -> str | None:
    return value or None


def _register_cancel_token_metadata(
    stream_id: str,
    *,
    owner_user_id: str | None,
    project_id: str | None,
) -> None:
    cancel_token_metadata[stream_id] = CancelTokenMetadata(
        owner_user_id=_normalize_identity(owner_user_id),
        project_id=_normalize_identity(project_id),
    )


def _cancel_token_metadata_matches(
    stream_id: str,
    *,
    owner_user_id: str | None,
    project_id: str | None,
) -> bool:
    metadata = cancel_token_metadata.get(stream_id)
    if metadata is None:
        return False

    request_owner = _normalize_identity(owner_user_id)
    request_project = _normalize_identity(project_id)

    if metadata.owner_user_id is not None and metadata.owner_user_id != request_owner:
        return False
    if metadata.project_id is not None and metadata.project_id != request_project:
        return False
    return True


def create_cancel_token(
    stream_id: str,
    *,
    owner_user_id: str | None = None,
    project_id: str | None = None,
) -> asyncio.Event:
    """Create an owned token without replacing an active base token."""
    if stream_id in _base._tokens:
        raise ValueError(f"Cancel token for stream '{stream_id}' already exists.")

    event = _base.create_cancel_token(stream_id)
    _register_cancel_token_metadata(stream_id, owner_user_id=owner_user_id, project_id=project_id)
    return event


def cancel_stream(
    stream_id: str,
    *,
    owner_user_id: str | None = None,
    project_id: str | None = None,
) -> bool:
    """Cancel a token only when its downstream ownership metadata matches."""
    if not _cancel_token_metadata_matches(
        stream_id,
        owner_user_id=owner_user_id,
        project_id=project_id,
    ):
        return False
    return _base.cancel_stream(stream_id)


def cleanup_cancel_token(stream_id: str) -> None:
    """Remove the base token and its downstream ownership metadata."""
    _base.cleanup_cancel_token(stream_id)
    cancel_token_metadata.pop(stream_id, None)

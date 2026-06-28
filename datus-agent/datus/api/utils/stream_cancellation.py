"""Lightweight SSE stream cancellation token management."""

import asyncio
from dataclasses import dataclass

_tokens: dict[str, asyncio.Event] = {}
_token_metadata: dict[str, "_CancelTokenMetadata"] = {}


@dataclass(frozen=True)
class _CancelTokenMetadata:
    owner_user_id: str | None = None
    project_id: str | None = None


def _normalize_identity(value: str | None) -> str | None:
    return value or None


def _metadata_matches(
    metadata: _CancelTokenMetadata,
    *,
    owner_user_id: str | None,
    project_id: str | None,
) -> bool:
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
    """Create a cancellation token for a stream."""
    if stream_id in _tokens:
        raise ValueError(f"Cancel token for stream '{stream_id}' already exists.")
    event = asyncio.Event()
    _tokens[stream_id] = event
    _token_metadata[stream_id] = _CancelTokenMetadata(
        owner_user_id=_normalize_identity(owner_user_id),
        project_id=_normalize_identity(project_id),
    )
    return event


def cancel_stream(
    stream_id: str,
    *,
    owner_user_id: str | None = None,
    project_id: str | None = None,
) -> bool:
    """Signal cancellation for a stream. Returns True if the token existed."""
    event = _tokens.get(stream_id)
    if not event:
        return False

    metadata = _token_metadata.get(stream_id, _CancelTokenMetadata())
    if not _metadata_matches(metadata, owner_user_id=owner_user_id, project_id=project_id):
        return False

    event.set()
    return True


def cleanup_cancel_token(stream_id: str) -> None:
    """Remove a cancellation token after stream ends."""
    _tokens.pop(stream_id, None)
    _token_metadata.pop(stream_id, None)

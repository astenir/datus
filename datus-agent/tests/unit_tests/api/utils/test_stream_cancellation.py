"""Tests for datus.api.utils.stream_cancellation — SSE cancel token management."""

import pytest

from datus.api.utils import stream_cancellation
from datus.api.utils.stream_cancellation import (
    cancel_stream,
    cleanup_cancel_token,
    create_cancel_token,
)


@pytest.fixture(autouse=True)
def _clear_tokens():
    """Ensure token dict is clean before/after each test."""
    stream_cancellation._tokens.clear()
    stream_cancellation._token_metadata.clear()
    yield
    stream_cancellation._tokens.clear()
    stream_cancellation._token_metadata.clear()


class TestCreateCancelToken:
    """Tests for create_cancel_token lifecycle."""

    def test_creates_asyncio_event(self):
        """Token is an asyncio.Event registered in the global dict."""
        import asyncio

        event = create_cancel_token("stream-1")
        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_token_stored_by_stream_id(self):
        """Created token is retrievable by stream_id."""
        event = create_cancel_token("stream-abc")
        assert stream_cancellation._tokens["stream-abc"] is event

    def test_rejects_duplicate_token_id(self):
        """Creating a token with the same ID must not replace the active stream."""
        old = create_cancel_token("dup")

        with pytest.raises(ValueError, match="already exists"):
            create_cancel_token("dup")

        assert stream_cancellation._tokens["dup"] is old


class TestCancelStream:
    """Tests for cancel_stream signaling."""

    def test_cancel_existing_stream_returns_true(self):
        """Cancelling an existing stream sets the event and returns True."""
        event = create_cancel_token("s1")
        result = cancel_stream("s1")
        assert result is True
        assert event.is_set()

    def test_cancel_nonexistent_stream_returns_false(self):
        """Cancelling a stream that doesn't exist returns False."""
        result = cancel_stream("nonexistent")
        assert result is False

    def test_cancel_idempotent(self):
        """Cancelling the same stream twice still returns True."""
        create_cancel_token("s2")
        assert cancel_stream("s2") is True
        assert cancel_stream("s2") is True

    def test_cancel_rejects_foreign_owner(self):
        """A stream bound to one user cannot be cancelled by another user."""
        event = create_cancel_token("owned", owner_user_id="alice", project_id="proj")

        result = cancel_stream("owned", owner_user_id="bob", project_id="proj")

        assert result is False
        assert not event.is_set()

    def test_cancel_allows_matching_owner(self):
        """A stream bound to a user can be cancelled by that same user."""
        event = create_cancel_token("owned", owner_user_id="alice", project_id="proj")

        result = cancel_stream("owned", owner_user_id="alice", project_id="proj")

        assert result is True
        assert event.is_set()

    def test_cancel_rejects_project_mismatch(self):
        """A project-bound stream cannot be cancelled from a different project."""
        event = create_cancel_token("project-stream", owner_user_id="alice", project_id="proj-a")

        result = cancel_stream("project-stream", owner_user_id="alice", project_id="proj-b")

        assert result is False
        assert not event.is_set()


class TestCleanupCancelToken:
    """Tests for cleanup_cancel_token removal."""

    def test_cleanup_removes_token(self):
        """Cleanup removes the token from the global dict."""
        create_cancel_token("to-clean")
        cleanup_cancel_token("to-clean")
        assert "to-clean" not in stream_cancellation._tokens

    def test_cleanup_nonexistent_is_noop(self):
        """Cleanup of non-existent token doesn't raise."""
        cleanup_cancel_token("ghost")
        assert "ghost" not in stream_cancellation._tokens

    def test_full_lifecycle(self):
        """Create → cancel → cleanup: each step works as expected."""
        event = create_cancel_token("lifecycle")
        assert not event.is_set()
        assert cancel_stream("lifecycle") is True
        assert event.is_set()
        cleanup_cancel_token("lifecycle")
        assert "lifecycle" not in stream_cancellation._tokens

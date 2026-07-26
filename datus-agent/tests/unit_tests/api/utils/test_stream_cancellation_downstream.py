"""Downstream ownership checks for SSE cancellation tokens."""

import pytest

from datus.api.utils import stream_cancellation
from datus.api.utils import stream_cancellation_metadata as secure_cancellation


@pytest.fixture(autouse=True)
def _clear_tokens():
    stream_cancellation._tokens.clear()
    secure_cancellation.cancel_token_metadata.clear()
    yield
    stream_cancellation._tokens.clear()
    secure_cancellation.cancel_token_metadata.clear()


def test_create_rejects_duplicate_without_overwriting_active_token():
    old_event = secure_cancellation.create_cancel_token(
        "duplicate",
        owner_user_id="alice",
        project_id="project-a",
    )

    with pytest.raises(ValueError, match="already exists"):
        secure_cancellation.create_cancel_token(
            "duplicate",
            owner_user_id="bob",
            project_id="project-b",
        )

    assert stream_cancellation._tokens["duplicate"] is old_event


def test_cancel_rejects_foreign_owner():
    event = secure_cancellation.create_cancel_token(
        "owned",
        owner_user_id="alice",
        project_id="project-a",
    )

    cancelled = secure_cancellation.cancel_stream(
        "owned",
        owner_user_id="bob",
        project_id="project-a",
    )

    assert cancelled is False
    assert not event.is_set()


def test_cancel_accepts_matching_owner_and_project():
    event = secure_cancellation.create_cancel_token(
        "owned",
        owner_user_id="alice",
        project_id="project-a",
    )

    cancelled = secure_cancellation.cancel_stream(
        "owned",
        owner_user_id="alice",
        project_id="project-a",
    )

    assert cancelled is True
    assert event.is_set()


def test_cancel_rejects_wrong_project():
    event = secure_cancellation.create_cancel_token(
        "owned",
        owner_user_id="alice",
        project_id="project-a",
    )

    cancelled = secure_cancellation.cancel_stream(
        "owned",
        owner_user_id="alice",
        project_id="project-b",
    )

    assert cancelled is False
    assert not event.is_set()


def test_cancel_rejects_base_token_without_ownership_metadata():
    event = stream_cancellation.create_cancel_token("legacy")

    cancelled = secure_cancellation.cancel_stream(
        "legacy",
        owner_user_id="alice",
        project_id="project-a",
    )

    assert cancelled is False
    assert not event.is_set()


def test_cleanup_removes_base_token_and_metadata():
    secure_cancellation.create_cancel_token(
        "cleanup",
        owner_user_id="alice",
        project_id="project-a",
    )

    secure_cancellation.cleanup_cancel_token("cleanup")

    assert "cleanup" not in stream_cancellation._tokens
    assert "cleanup" not in secure_cancellation.cancel_token_metadata

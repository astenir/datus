"""Downstream SessionManager coverage kept out of the upstream test file."""

from datus.models.session_manager import session_scope_from_user_id


def test_session_scope_from_user_id_keeps_safe_ids_readable():
    assert session_scope_from_user_id("alice_123") == "alice_123"


def test_session_scope_from_user_id_hashes_unsafe_ids():
    scope = session_scope_from_user_id("alice@example.com")

    assert scope is not None
    assert scope.startswith("alice_example_com_")
    assert "/" not in scope
    assert "@" not in scope
    assert "." not in scope
    assert len(scope.rsplit("_", 1)[-1]) == 12

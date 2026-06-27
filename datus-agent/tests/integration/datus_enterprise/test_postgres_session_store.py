"""Opt-in PostgreSQL integration tests for enterprise session body storage."""

from __future__ import annotations

import os
import uuid

import pytest

from datus_enterprise.postgres_session_store import PgSessionBodyStore

pytestmark = pytest.mark.skipif(
    not os.getenv("DATUS_ENTERPRISE_PG_DSN"),
    reason="DATUS_ENTERPRISE_PG_DSN is required for PostgreSQL session body integration tests.",
)


@pytest.mark.asyncio
async def test_pg_session_body_store_round_trip_and_cleanup():
    dsn = os.environ["DATUS_ENTERPRISE_PG_DSN"]
    prefix = f"it_{uuid.uuid4().hex[:12]}"
    project_id = f"{prefix}_project"
    scope = f"{prefix}_alice"
    session_id = f"chat_session_{prefix}"
    copied_session_id = f"feedback_session_{prefix}"
    store = PgSessionBodyStore(dsn=dsn, min_size=1, max_size=1)
    try:
        session = store.open_session(project_id=project_id, scope=scope, session_id=session_id)
        await session.add_items(
            [
                {"role": "user", "content": "hello pg"},
                {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
            ]
        )
        assert await session.get_items() == [
            {"role": "user", "content": "hello pg"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
        ]
        assert await store.session_exists(project_id=project_id, scope=scope, session_id=session_id) is True
        assert await store.list_session_ids(project_id=project_id, scope=scope) == [session_id]

        await store.upsert_running_turn_usage(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            user_turn_number=1,
            cumulative={"total_tokens": 123},
            context_length=4096,
        )
        running = await store.get_running_turn_usage(project_id=project_id, scope=scope, session_id=session_id)
        assert running["cumulative"]["total_tokens"] == 123

        await store.save_system_prompt_snapshot(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            payload={"schema_version": 1, "prompt": "system", "node_name": "chat"},
        )
        snapshot = await store.load_system_prompt_snapshot(project_id=project_id, scope=scope, session_id=session_id)
        assert snapshot["prompt"] == "system"

        await store.copy_session(
            project_id=project_id,
            scope=scope,
            source_session_id=session_id,
            target_session_id=copied_session_id,
        )
        copied_snapshot = await store.load_system_prompt_snapshot(
            project_id=project_id,
            scope=scope,
            session_id=copied_session_id,
        )
        assert copied_snapshot["prompt"] == "system"
    finally:
        await store.delete_session(project_id=project_id, scope=scope, session_id=session_id)
        await store.delete_session(project_id=project_id, scope=scope, session_id=copied_session_id)
        await store.close()

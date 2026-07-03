"""Opt-in OceanBase MySQL integration tests for enterprise session storage."""

from __future__ import annotations

import os
import uuid

import pytest

from datus_enterprise.oceanbase_session_store import ObSessionBodyStore
from datus_enterprise.oceanbase_stores import ObSessionOwnerStore

OB_HOST = os.getenv("DATUS_ENTERPRISE_OB_HOST")
OB_PORT = os.getenv("DATUS_ENTERPRISE_OB_PORT", "2881")
OB_USER = os.getenv("DATUS_ENTERPRISE_OB_USER")
OB_PASSWORD = os.getenv("DATUS_ENTERPRISE_OB_PASSWORD")
OB_DATABASE = os.getenv("DATUS_ENTERPRISE_OB_DATABASE", "datus_enterprise_it")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.nightly,
    pytest.mark.skipif(
        not (OB_HOST and OB_USER and OB_PASSWORD),
        reason="DATUS_ENTERPRISE_OB_HOST/USER/PASSWORD are required for OceanBase session integration tests.",
    ),
]


@pytest.mark.asyncio
async def test_oceanbase_session_owner_and_body_round_trip():
    prefix = f"it_{uuid.uuid4().hex[:12]}"
    project_id = f"{prefix}_project"
    user_id = f"{prefix}_alice"
    scope = user_id
    session_id = f"chat_session_{prefix}"
    copied_session_id = f"feedback_session_{prefix}"
    owner_store = _owner_store()
    body_store = _body_store()

    try:
        await owner_store.set_owner(project_id, session_id, user_id)
        assert await owner_store.get_owner(project_id, session_id) == user_id
        assert await owner_store.list_session_ids(project_id, user_id) == [session_id]

        session = body_store.open_session(project_id=project_id, scope=scope, session_id=session_id)
        await session.add_items(
            [
                {"role": "user", "content": "hello oceanbase"},
                {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
            ]
        )
        assert await session.get_items() == [
            {"role": "user", "content": "hello oceanbase"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
        ]
        assert await body_store.session_exists(project_id=project_id, scope=scope, session_id=session_id) is True
        assert await body_store.list_session_ids(project_id=project_id, scope=scope) == [session_id]

        info = await body_store.get_session_info(project_id=project_id, scope=scope, session_id=session_id)
        assert info["exists"] is True
        assert info["message_count"] == 2
        assert info["latest_user_message"] == "hello oceanbase"

        await body_store.upsert_running_turn_usage(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            user_turn_number=1,
            cumulative={"total_tokens": 123},
            context_length=4096,
        )
        running = await body_store.get_running_turn_usage(project_id=project_id, scope=scope, session_id=session_id)
        assert running["cumulative"]["total_tokens"] == 123

        await body_store.save_system_prompt_snapshot(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            payload={"schema_version": 1, "prompt": "system", "node_name": "chat"},
        )
        snapshot = await body_store.load_system_prompt_snapshot(project_id=project_id, scope=scope, session_id=session_id)
        assert snapshot["prompt"] == "system"

        await body_store.copy_session(
            project_id=project_id,
            scope=scope,
            source_session_id=session_id,
            target_session_id=copied_session_id,
        )
        assert sorted(await body_store.list_session_ids(project_id=project_id, scope=scope)) == [
            session_id,
            copied_session_id,
        ]
        assert await body_store.load_system_prompt_snapshot(
            project_id=project_id,
            scope=scope,
            session_id=copied_session_id,
        ) == snapshot
    finally:
        await owner_store.delete_owner(project_id, session_id)
        await body_store.delete_session(project_id=project_id, scope=scope, session_id=session_id)
        await body_store.delete_session(project_id=project_id, scope=scope, session_id=copied_session_id)
        await owner_store.close()
        await body_store.close()


def _owner_store() -> ObSessionOwnerStore:
    return ObSessionOwnerStore(
        host=OB_HOST or "",
        port=OB_PORT,
        user=OB_USER or "",
        password=OB_PASSWORD or "",
        database=OB_DATABASE,
        pool_max_size=1,
    )


def _body_store() -> ObSessionBodyStore:
    return ObSessionBodyStore(
        host=OB_HOST or "",
        port=OB_PORT,
        user=OB_USER or "",
        password=OB_PASSWORD or "",
        database=OB_DATABASE,
        pool_max_size=1,
    )

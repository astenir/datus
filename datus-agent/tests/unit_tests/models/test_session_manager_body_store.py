"""SessionManager tests for pluggable session body backends."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from datus.models.session_manager import SessionManager


class _MemorySession:
    def __init__(self, store: "_MemoryBodyStore", project_id: str, scope: str | None, session_id: str) -> None:
        self._store = store
        self._project_id = project_id
        self._scope = scope or ""
        self.session_id = session_id

    @property
    def _key(self) -> tuple[str, str, str]:
        return (self._project_id, self._scope, self.session_id)

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        rows = self._store.messages.setdefault(self._key, [])
        for item in items:
            rows.append({"message_data": self._store.dumps(item), "created_at": "2026-01-01T00:00:00Z"})
        self._store.sessions.add(self._key)

    async def get_items(self, limit: int | None = None, branch_id: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        items = [self._store.loads(row["message_data"]) for row in self._store.messages.get(self._key, [])]
        return items[-limit:] if limit is not None else items

    async def clear_session(self) -> None:
        self._store.messages.pop(self._key, None)
        self._store.sessions.discard(self._key)


class _MemoryBodyStore:
    def __init__(self) -> None:
        import json

        self.dumps = lambda item: json.dumps(item, ensure_ascii=False)
        self.loads = json.loads
        self.sessions: set[tuple[str, str, str]] = set()
        self.messages: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self.running: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.snapshots: dict[tuple[str, str, str], dict[str, Any]] = {}

    def open_session(self, *, project_id: str, scope: str | None, session_id: str) -> _MemorySession:
        return _MemorySession(self, project_id, scope, session_id)

    async def session_exists(self, *, project_id: str, scope: str | None, session_id: str) -> bool:
        return (project_id, scope or "", session_id) in self.sessions

    async def list_session_ids(
        self,
        *,
        project_id: str,
        scope: str | None,
        limit: int | None = None,
        sort_by_modified: bool = False,  # noqa: ARG002
    ) -> list[str]:
        ids = sorted(sid for project, scoped, sid in self.sessions if project == project_id and scoped == (scope or ""))
        return ids[:limit] if limit is not None else ids

    async def get_session_info(self, *, project_id: str, scope: str | None, session_id: str) -> dict[str, Any]:
        key = (project_id, scope or "", session_id)
        if key not in self.sessions:
            return {"exists": False}
        rows = self.messages.get(key, [])
        first_user = None
        for row in rows:
            payload = self.loads(row["message_data"])
            if payload.get("role") == "user":
                first_user = payload.get("content")
                break
        return {
            "exists": True,
            "session_id": session_id,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:01Z",
            "message_count": len(rows),
            "total_tokens": 0,
            "first_user_message": first_user,
        }

    async def delete_session(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        key = (project_id, scope or "", session_id)
        self.sessions.discard(key)
        self.messages.pop(key, None)
        self.running.pop(key, None)
        self.snapshots.pop(key, None)

    async def copy_session(
        self,
        *,
        project_id: str,
        scope: str | None,
        source_session_id: str,
        target_session_id: str,
    ) -> None:
        source = (project_id, scope or "", source_session_id)
        target = (project_id, scope or "", target_session_id)
        if source not in self.sessions:
            return
        self.sessions.add(target)
        self.messages[target] = list(self.messages.get(source, []))
        if source in self.snapshots:
            self.snapshots[target] = dict(self.snapshots[source])

    async def get_session_messages(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> list[dict[str, Any]]:
        return list(self.messages.get((project_id, scope or "", session_id), []))

    async def get_detailed_usage(self, *, project_id: str, scope: str | None, session_id: str) -> dict[str, Any]:
        running = self.running.get((project_id, scope or "", session_id))
        total = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
        if running:
            for key, value in running.get("cumulative", {}).items():
                if key in total:
                    total[key] += int(value)
        return {"total": total, "turns": [], "turn_count": 0, "running": running}

    async def upsert_running_turn_usage(
        self,
        *,
        project_id: str,
        scope: str | None,
        session_id: str,
        user_turn_number: int,
        cumulative: dict[str, Any],
        context_length: int,
    ) -> None:
        self.running[(project_id, scope or "", session_id)] = {
            "user_turn_number": user_turn_number,
            "cumulative": cumulative,
            "context_length": context_length,
            "updated_at": "2026-01-01T00:00:01Z",
        }

    async def get_running_turn_usage(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> dict[str, Any] | None:
        return self.running.get((project_id, scope or "", session_id))

    async def clear_running_turn_usage(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        self.running.pop((project_id, scope or "", session_id), None)

    async def save_system_prompt_snapshot(
        self, *, project_id: str, scope: str | None, session_id: str, payload: dict[str, Any]
    ) -> None:
        self.snapshots[(project_id, scope or "", session_id)] = dict(payload)

    async def load_system_prompt_snapshot(self, *, project_id: str, scope: str | None, session_id: str):
        return self.snapshots.get((project_id, scope or "", session_id))

    async def delete_system_prompt_snapshot(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        self.snapshots.pop((project_id, scope or "", session_id), None)


@pytest.mark.asyncio
async def test_body_store_create_list_history_copy_and_delete(tmp_path):
    store = _MemoryBodyStore()
    manager = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="alice",
        project_id="enterprise",
        body_store=store,
    )
    session = manager.create_session("chat_session_a")
    await session.add_items(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "hi"}]},
        ]
    )

    assert manager.session_exists("chat_session_a") is True
    assert manager.list_sessions() == ["chat_session_a"]
    assert manager.get_session_info("chat_session_a")["first_user_message"] == "hello"
    assert manager.get_session_messages("chat_session_a")[0]["content"] == "hello"

    manager.save_system_prompt_snapshot("chat_session_a", "prompt", {"node_name": "chat"})
    copied = manager.copy_session("chat_session_a", "feedback")
    assert copied.startswith("feedback_session_")
    assert manager.session_exists(copied) is True
    assert manager.load_system_prompt_snapshot(copied)["prompt"] == "prompt"

    manager.delete_session("chat_session_a")
    assert manager.session_exists("chat_session_a") is False


@pytest.mark.asyncio
async def test_body_store_scope_isolation_and_invalid_session_guard(tmp_path):
    store = _MemoryBodyStore()
    alice = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="alice",
        project_id="enterprise",
        body_store=store,
    )
    bob = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="bob",
        project_id="enterprise",
        body_store=store,
    )
    await alice.create_session("chat_session_shared").add_items([{"role": "user", "content": "alice"}])

    assert alice.session_exists("chat_session_shared") is True
    assert bob.session_exists("chat_session_shared") is False
    with pytest.raises(ValueError, match="Invalid session ID"):
        alice.session_exists("../chat_session_shared")


@pytest.mark.asyncio
async def test_body_store_async_methods_do_not_use_run_async(tmp_path, monkeypatch):
    import datus.models.session_manager as session_manager_module

    def fail_run_async(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("async body-store methods must not use run_async")

    monkeypatch.setattr(session_manager_module, "run_async", fail_run_async)
    store = _MemoryBodyStore()
    manager = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="alice",
        project_id="enterprise",
        body_store=store,
    )
    await manager.create_session("chat_session_async").add_items([{"role": "user", "content": "hello"}])

    await manager.save_system_prompt_snapshot_async("chat_session_async", "prompt", {"node_name": "chat"})
    snapshot = await manager.load_system_prompt_snapshot_async("chat_session_async")
    assert snapshot["prompt"] == "prompt"

    await manager.upsert_running_turn_usage_async("chat_session_async", 1, {"total_tokens": 7}, 128)
    running = await manager.get_running_turn_usage_async("chat_session_async")
    assert running["cumulative"]["total_tokens"] == 7
    await manager.clear_running_turn_usage_async("chat_session_async")
    assert await manager.get_running_turn_usage_async("chat_session_async") is None

    copied = await manager.copy_session_async("chat_session_async", "feedback")
    assert copied.startswith("feedback_session_")
    assert await store.session_exists(project_id="enterprise", scope="alice", session_id=copied) is True

    await manager.delete_system_prompt_snapshot_async("chat_session_async")
    assert await manager.load_system_prompt_snapshot_async("chat_session_async") is None


def test_body_store_running_usage_and_snapshot_round_trip(tmp_path):
    store = _MemoryBodyStore()
    manager = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="alice",
        project_id="enterprise",
        body_store=store,
    )
    manager.upsert_running_turn_usage("chat_session_usage", 2, {"total_tokens": 42}, 1000)
    assert manager.get_running_turn_usage("chat_session_usage")["cumulative"]["total_tokens"] == 42
    assert manager.get_detailed_usage("chat_session_usage")["total"]["total_tokens"] == 42
    manager.clear_running_turn_usage("chat_session_usage")
    assert manager.get_running_turn_usage("chat_session_usage") is None

    manager.save_system_prompt_snapshot("chat_session_usage", "prompt", {"node_name": "chat"})
    assert manager.load_system_prompt_snapshot("chat_session_usage")["prompt"] == "prompt"
    manager.delete_system_prompt_snapshot("chat_session_usage")
    assert manager.load_system_prompt_snapshot("chat_session_usage") is None


def test_body_store_project_id_can_come_from_agent_config(tmp_path):
    store = _MemoryBodyStore()
    config = SimpleNamespace(_session_project_id="project-from-config")
    manager = SessionManager(
        session_dir=str(tmp_path / "sessions"),
        scope="alice",
        agent_config=config,
        body_store=store,
    )
    assert manager.project_id == "project-from-config"

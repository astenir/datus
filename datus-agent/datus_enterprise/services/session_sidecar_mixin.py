"""Display-only session sidecar persistence for downstream SessionManager."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import Any, Dict, List

from datus.api.models.downstream import ChatSessionSubagentEvent, ChatSessionTerminalEvent
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


class SessionSidecarMixin:
    """Persist terminal and delegated-session facts outside SDK history."""

    @staticmethod
    def _terminal_event_table_sql() -> str:
        return (
            "CREATE TABLE IF NOT EXISTS chat_session_terminal_events ("
            "event_id TEXT PRIMARY KEY, "
            "session_id TEXT NOT NULL, "
            "event_type TEXT NOT NULL, "
            "payload_json TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )

    def append_terminal_event(self, session_id: str, event: ChatSessionTerminalEvent | Dict[str, Any]) -> None:
        """Idempotently persist a display-only terminal event beside SDK history."""
        self._validate_session_id(session_id)
        terminal_event = ChatSessionTerminalEvent.model_validate(event)
        if self._body_store is not None:
            self._run_body_store_sync(
                lambda: self._body_store.append_session_terminal_event(
                    **self._store_kwargs(session_id),
                    event=terminal_event.model_dump(),
                )
            )
            return

        db_path = os.path.join(self.session_dir, f"{session_id}.db")
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute(self._terminal_event_table_sql())
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_session_terminal_events_created "
                "ON chat_session_terminal_events(session_id, created_at, event_id)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO chat_session_terminal_events "
                "(event_id, session_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    terminal_event.event_id,
                    session_id,
                    terminal_event.event_type,
                    terminal_event.model_dump_json(),
                    terminal_event.created_at,
                ),
            )

    async def append_terminal_event_async(
        self, session_id: str, event: ChatSessionTerminalEvent | Dict[str, Any]
    ) -> None:
        """Persist a terminal event without crossing async body-store loops."""
        self._validate_session_id(session_id)
        terminal_event = ChatSessionTerminalEvent.model_validate(event)
        if self._body_store is not None:
            await self._body_store.append_session_terminal_event(
                **self._store_kwargs(session_id),
                event=terminal_event.model_dump(),
            )
            return
        await asyncio.to_thread(self.append_terminal_event, session_id, terminal_event)

    def append_subagent_event(self, session_id: str, event: ChatSessionSubagentEvent | Dict[str, Any]) -> None:
        """Idempotently persist a display-only parent-to-child session link."""
        self._validate_session_id(session_id)
        subagent_event = ChatSessionSubagentEvent.model_validate(event)
        if self._body_store is not None:
            self._run_body_store_sync(
                lambda: self._body_store.append_session_terminal_event(
                    **self._store_kwargs(session_id),
                    event=subagent_event.model_dump(),
                )
            )
            return

        db_path = os.path.join(self.session_dir, f"{session_id}.db")
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute(self._terminal_event_table_sql())
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_session_terminal_events_created "
                "ON chat_session_terminal_events(session_id, created_at, event_id)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO chat_session_terminal_events "
                "(event_id, session_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    subagent_event.event_id,
                    session_id,
                    subagent_event.event_type,
                    subagent_event.model_dump_json(),
                    subagent_event.created_at,
                ),
            )

    async def append_subagent_event_async(
        self, session_id: str, event: ChatSessionSubagentEvent | Dict[str, Any]
    ) -> None:
        """Persist a delegation link without crossing async body-store loops."""
        self._validate_session_id(session_id)
        subagent_event = ChatSessionSubagentEvent.model_validate(event)
        if self._body_store is not None:
            await self._body_store.append_session_terminal_event(
                **self._store_kwargs(session_id),
                event=subagent_event.model_dump(),
            )
            return
        await asyncio.to_thread(self.append_subagent_event, session_id, subagent_event)

    def get_terminal_events(self, session_id: str) -> List[ChatSessionTerminalEvent]:
        """Load valid terminal events without creating history for missing sessions."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            rows = self._run_body_store_sync(
                lambda: self._body_store.get_session_terminal_events(**self._store_kwargs(session_id))
            )
            return self._validate_terminal_events(rows, session_id=session_id)

        db_path = os.path.join(self.session_dir, f"{session_id}.db")
        if not os.path.exists(db_path):
            return []
        try:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                rows = conn.execute(
                    "SELECT payload_json FROM chat_session_terminal_events "
                    "WHERE session_id = ? ORDER BY created_at, event_id",
                    (session_id,),
                ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
        return self._validate_terminal_events((row[0] for row in rows), session_id=session_id)

    async def get_terminal_events_async(self, session_id: str) -> List[ChatSessionTerminalEvent]:
        """Load terminal events without crossing async body-store loops."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            rows = await self._body_store.get_session_terminal_events(**self._store_kwargs(session_id))
            return self._validate_terminal_events(rows, session_id=session_id)
        return await asyncio.to_thread(self.get_terminal_events, session_id)

    def get_subagent_events(self, session_id: str) -> List[ChatSessionSubagentEvent]:
        """Load valid display-only delegation links for a parent session."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            rows = self._run_body_store_sync(
                lambda: self._body_store.get_session_terminal_events(**self._store_kwargs(session_id))
            )
            return self._validate_subagent_events(rows, session_id=session_id)

        db_path = os.path.join(self.session_dir, f"{session_id}.db")
        if not os.path.exists(db_path):
            return []
        try:
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                rows = conn.execute(
                    "SELECT payload_json FROM chat_session_terminal_events "
                    "WHERE session_id = ? ORDER BY created_at, event_id",
                    (session_id,),
                ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
        return self._validate_subagent_events((row[0] for row in rows), session_id=session_id)

    async def get_subagent_events_async(self, session_id: str) -> List[ChatSessionSubagentEvent]:
        """Load delegation links without crossing async body-store loops."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            rows = await self._body_store.get_session_terminal_events(**self._store_kwargs(session_id))
            return self._validate_subagent_events(rows, session_id=session_id)
        return await asyncio.to_thread(self.get_subagent_events, session_id)

    @staticmethod
    def _validate_terminal_events(rows: Any, *, session_id: str) -> List[ChatSessionTerminalEvent]:
        events: List[ChatSessionTerminalEvent] = []
        for row in rows or []:
            try:
                payload = json.loads(row) if isinstance(row, str) else row
                if isinstance(payload, dict) and payload.get("event_type") not in {
                    "error",
                    "cancelled",
                    "timeout",
                }:
                    continue
                events.append(ChatSessionTerminalEvent.model_validate(payload))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping malformed terminal event for session %s: %s", session_id, exc)
        return events

    @staticmethod
    def _validate_subagent_events(rows: Any, *, session_id: str) -> List[ChatSessionSubagentEvent]:
        events: List[ChatSessionSubagentEvent] = []
        for row in rows or []:
            try:
                payload = json.loads(row) if isinstance(row, str) else row
                if isinstance(payload, dict) and payload.get("event_type") != "subagent":
                    continue
                events.append(ChatSessionSubagentEvent.model_validate(payload))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping malformed subagent event for session %s: %s", session_id, exc)
        return events

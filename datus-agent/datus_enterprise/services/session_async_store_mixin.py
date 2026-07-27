"""Async adapters for downstream SessionManager body-store operations."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


class SessionAsyncStoreMixin:
    """Keep async request paths on the body store's owning event loop."""

    async def save_system_prompt_snapshot_async(
        self,
        session_id: str,
        prompt: str,
        meta: Dict[str, Any],
    ) -> None:
        """Persist a system-prompt snapshot without crossing event loops."""
        payload: Dict[str, Any] = {"schema_version": self._SNAPSHOT_SCHEMA_VERSION, "prompt": prompt, **meta}
        if self._body_store is not None:
            self._validate_session_id(session_id)
            await self._body_store.save_system_prompt_snapshot(**self._store_kwargs(session_id), payload=payload)
            return
        self.save_system_prompt_snapshot(session_id, prompt, meta)

    async def load_system_prompt_snapshot_async(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a system-prompt snapshot without crossing event loops."""
        if self._body_store is not None:
            self._validate_session_id(session_id)
            payload = await self._body_store.load_system_prompt_snapshot(**self._store_kwargs(session_id))
            return self._validate_system_prompt_snapshot_payload(payload)
        return self.load_system_prompt_snapshot(session_id)

    async def delete_system_prompt_snapshot_async(self, session_id: str) -> None:
        """Delete a system-prompt snapshot without crossing event loops."""
        if self._body_store is not None:
            self._validate_session_id(session_id)
            await self._body_store.delete_system_prompt_snapshot(**self._store_kwargs(session_id))
            return
        self.delete_system_prompt_snapshot(session_id)

    async def copy_session_async(self, source_session_id: str, target_node_name: str) -> str:
        """Copy a session from async request code without crossing event loops."""
        self._validate_session_id(source_session_id)
        new_session_id = f"{target_node_name}_session_{uuid.uuid4().hex[:8]}"
        if self._body_store is not None:
            if await self._body_store.session_exists(**self._store_kwargs(source_session_id)):
                await self._body_store.copy_session(
                    project_id=self.project_id,
                    scope=self._scope,
                    source_session_id=source_session_id,
                    target_session_id=new_session_id,
                )
                self._sessions[new_session_id] = self._body_store.open_session(
                    project_id=self.project_id,
                    scope=self._scope,
                    session_id=new_session_id,
                )
            return new_session_id
        return self.copy_session(source_session_id, target_node_name)

    async def upsert_running_turn_usage_async(
        self,
        session_id: str,
        user_turn_number: int,
        cumulative: Dict[str, Any],
        context_length: int,
    ) -> None:
        """Persist running turn usage without crossing event loops."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            await self._body_store.upsert_running_turn_usage(
                **self._store_kwargs(session_id),
                user_turn_number=user_turn_number,
                cumulative=cumulative,
                context_length=context_length,
            )
            return
        self.upsert_running_turn_usage(session_id, user_turn_number, cumulative, context_length)

    async def get_running_turn_usage_async(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return running turn usage without crossing event loops."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            return await self._body_store.get_running_turn_usage(**self._store_kwargs(session_id))
        return self.get_running_turn_usage(session_id)

    async def clear_running_turn_usage_async(self, session_id: str) -> None:
        """Drop running turn usage without crossing event loops."""
        self._validate_session_id(session_id)
        if self._body_store is not None:
            await self._body_store.clear_running_turn_usage(**self._store_kwargs(session_id))
            return
        self.clear_running_turn_usage(session_id)

"""Enterprise Chat service adapters composed from focused domain mixins."""

import asyncio
import copy
from typing import Any, Dict, Optional

from datus.api.models.base_models import Result
from datus.api.models.cli_models import (
    ChatSessionData,
    ChatSessionItemInfo,
    SSEErrorData,
    SSEEvent,
)
from datus.configuration.agent_config import AgentConfig
from datus.models.session_manager import (
    session_matches_agent,
    session_scope_from_user_id,
)
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso
from datus_enterprise.services.chat_history_reconstruction import EnterpriseChatHistoryMixin
from datus_enterprise.services.success_story_source import (
    EnterpriseSuccessStorySourceMixin,
    SuccessStorySourceError,
)

logger = get_logger(__name__)


class EnterpriseChatServiceMixin(EnterpriseSuccessStorySourceMixin, EnterpriseChatHistoryMixin):
    @staticmethod
    def _stream_start_error_event(error: Exception, error_type: str, session_id: str) -> SSEEvent:
        return SSEEvent(
            id=1,
            event="error",
            data=SSEErrorData(error=str(error), error_type=error_type, session_id=session_id),
            timestamp=now_utc_iso(),
        )

    async def session_exists_async(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Check if a session exists without crossing event loops for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.session_exists, session_id, user_id=user_id)

        scope = session_scope_from_user_id(user_id)
        return bool(
            await self._session_body_store.session_exists(
                project_id=self._project_id,
                scope=scope,
                session_id=session_id,
            )
        )

    async def list_sessions_async(
        self,
        user_id: Optional[str] = None,
        subagent_id: Optional[str] = None,
    ) -> Result[ChatSessionData]:
        """List chat sessions without using sync async bridges for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.list_sessions, user_id=user_id, subagent_id=subagent_id)

        scope = session_scope_from_user_id(user_id)
        try:
            all_ids = await self._session_body_store.list_session_ids(
                project_id=self._project_id,
                scope=scope,
            )
            if subagent_id is not None:
                all_ids = [sid for sid in all_ids if session_matches_agent(sid, subagent_id)]

            sessions = []
            for sid in all_ids:
                try:
                    info = await self._session_body_store.get_session_info(
                        project_id=self._project_id,
                        scope=scope,
                        session_id=sid,
                    )
                    if not info.get("exists", False):
                        continue
                    created_at = info.get("created_at") or ""
                    last_updated = info.get("updated_at") or info.get("file_modified_iso") or created_at
                    sessions.append(
                        ChatSessionItemInfo(
                            user_query=info.get("first_user_message"),
                            session_id=sid,
                            created_at=created_at,
                            last_updated=last_updated,
                            total_turns=info.get("message_count", 0),
                            token_count=info.get("total_tokens", 0),
                            last_sql_queries=[],
                            is_active=False,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read session {sid}: {e}")

            sessions = self._merge_runtime_sessions(
                sessions,
                user_id=user_id,
                subagent_id=subagent_id,
            )
            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=sessions,
                    total_count=len(sessions),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_LIST_ERROR", errorMessage=str(e))

    async def delete_session_async(self, session_id: str, user_id: Optional[str] = None) -> Result[ChatSessionData]:
        """Delete a session without using sync async bridges for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.delete_session, session_id, user_id=user_id)

        try:
            scope = session_scope_from_user_id(user_id)
            if await self._session_body_store.session_exists(
                project_id=self._project_id,
                scope=scope,
                session_id=session_id,
            ):
                await self._session_body_store.delete_session(
                    project_id=self._project_id,
                    scope=scope,
                    session_id=session_id,
                )

            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=[
                        ChatSessionItemInfo(
                            session_id=session_id,
                            created_at="",
                            last_updated=now_utc_iso(),
                            total_turns=0,
                            token_count=0,
                            last_sql_queries=[],
                            is_active=False,
                        )
                    ],
                    total_count=1,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_DELETE_ERROR", errorMessage=str(e))

    def get_session_info(self, session_id: str, user_id: Optional[str] = None) -> Result[Dict[str, Any]]:
        """Get scoped metadata for a chat session."""
        try:
            session_mgr = self._session_manager(user_id)
            return Result[Dict[str, Any]](success=True, data=session_mgr.get_session_info(session_id))
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return Result[Dict[str, Any]](success=False, errorCode="SESSION_INFO_ERROR", errorMessage=str(e))

    def _agent_config_for_session_body_store(self) -> AgentConfig:
        if self._session_body_store is None:
            return self.agent_config

        agent_config = copy.copy(self.agent_config)
        agent_config._session_body_store = self._session_body_store
        agent_config._session_project_id = self._project_id
        return agent_config


__all__ = ["EnterpriseChatServiceMixin", "SuccessStorySourceError"]

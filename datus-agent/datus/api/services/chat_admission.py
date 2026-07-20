"""Process-local admission control for long-running chat tasks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatAdmissionLimits:
    """Concurrent chat limits enforced within one API worker process."""

    global_limit: int = 32
    per_project_limit: int = 16
    per_user_limit: int = 4

    @classmethod
    def from_api_config(cls, api_config: dict[str, Any] | None) -> "ChatAdmissionLimits":
        raw = (api_config or {}).get("chat") or {}
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            global_limit=_positive_int(raw.get("max_active_global"), cls.global_limit),
            per_project_limit=_positive_int(raw.get("max_active_per_project"), cls.per_project_limit),
            per_user_limit=_positive_int(raw.get("max_active_per_user"), cls.per_user_limit),
        )


class ChatCapacityError(RuntimeError):
    """Raised when a chat request exceeds a configured concurrency limit."""

    def __init__(self, *, scope: str, limit: int) -> None:
        self.scope = scope
        self.limit = limit
        super().__init__(f"Chat capacity exceeded for {scope} (limit={limit}). Retry after another chat finishes.")


@dataclass
class ChatAdmissionToken:
    project_id: str
    user_id: str | None
    released: bool = False


class ChatAdmissionController:
    """Atomically track active chats across project-scoped services."""

    def __init__(self, limits: ChatAdmissionLimits | None = None) -> None:
        self.limits = limits or ChatAdmissionLimits()
        self._lock = asyncio.Lock()
        self._global_count = 0
        self._project_counts: dict[str, int] = {}
        self._user_counts: dict[str, int] = {}

    async def acquire(self, *, project_id: str, user_id: str | None) -> ChatAdmissionToken:
        project_key = project_id or "default"
        user_key = user_id or None
        async with self._lock:
            self._check_limit("worker", self._global_count, self.limits.global_limit)
            self._check_limit(
                f"project:{project_key}",
                self._project_counts.get(project_key, 0),
                self.limits.per_project_limit,
            )
            if user_key is not None:
                self._check_limit(
                    f"user:{user_key}",
                    self._user_counts.get(user_key, 0),
                    self.limits.per_user_limit,
                )
            self._global_count += 1
            self._project_counts[project_key] = self._project_counts.get(project_key, 0) + 1
            if user_key is not None:
                self._user_counts[user_key] = self._user_counts.get(user_key, 0) + 1
        return ChatAdmissionToken(project_id=project_key, user_id=user_key)

    async def release(self, token: ChatAdmissionToken | None) -> None:
        if token is None or token.released:
            return
        async with self._lock:
            if token.released:
                return
            token.released = True
            self._global_count = max(0, self._global_count - 1)
            _decrement(self._project_counts, token.project_id)
            if token.user_id is not None:
                _decrement(self._user_counts, token.user_id)

    @staticmethod
    def _check_limit(scope: str, current: int, limit: int) -> None:
        if current >= limit:
            raise ChatCapacityError(scope=scope, limit=limit)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _decrement(counts: dict[str, int], key: str) -> None:
    remaining = counts.get(key, 0) - 1
    if remaining > 0:
        counts[key] = remaining
    else:
        counts.pop(key, None)

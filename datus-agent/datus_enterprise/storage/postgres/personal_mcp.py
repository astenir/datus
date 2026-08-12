"""PostgreSQL store for personal MCP servers and session bindings."""

from __future__ import annotations

import json
import os
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.model_credentials import CredentialSecretCodec
from datus_enterprise.personal_mcp import token_hint
from datus_enterprise.storage.postgres.base import _PgStoreBase
from datus_enterprise.storage.postgres.records import _affected_rows


class PgUserMcpServerStore(_PgStoreBase):
    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 2,
        command_timeout: float | None = 30.0,
        encryption_secret: str | None = None,
    ) -> None:
        super().__init__(dsn, min_size=min_size, max_size=max_size, command_timeout=command_timeout)
        self._codec = CredentialSecretCodec(encryption_secret or os.getenv("DATUS_USER_MCP_SECRET"))

    async def list_servers(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch(f"{_SELECT} WHERE user_id = $1 ORDER BY created_at, mcp_id", user_id)
        return [self._record(row) for row in rows]

    async def get_server(self, user_id: str, mcp_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(f"{_SELECT} WHERE user_id = $1 AND mcp_id = $2", user_id, mcp_id)
        return self._record(row) if row else None

    async def put_server(
        self,
        *,
        user_id: str,
        mcp_id: str,
        display_name: str,
        transport: str,
        url: str,
        token: str | None,
        allowed_tools: list[str],
        blocked_tools: list[str],
        enabled: bool,
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO user_mcp_servers (
                user_id, mcp_id, display_name, transport, url, token_blob, token_hint,
                allowed_tools_json, blocked_tools_json, enabled, revision, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, 1, now(), now())
            ON CONFLICT(user_id, mcp_id) DO UPDATE SET
                display_name = excluded.display_name,
                transport = excluded.transport,
                url = excluded.url,
                token_blob = excluded.token_blob,
                token_hint = excluded.token_hint,
                allowed_tools_json = excluded.allowed_tools_json,
                blocked_tools_json = excluded.blocked_tools_json,
                enabled = excluded.enabled,
                revision = user_mcp_servers.revision + 1,
                updated_at = now()
            RETURNING user_id, mcp_id, display_name, transport, url, token_blob, token_hint,
                      allowed_tools_json, blocked_tools_json, enabled, revision, last_used_at,
                      created_at, updated_at
            """,
            user_id,
            mcp_id,
            display_name,
            transport,
            url,
            self._codec.encrypt(token) if token else None,
            token_hint(token),
            json.dumps(allowed_tools),
            json.dumps(blocked_tools),
            bool(enabled),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist personal MCP server.")
        return self._record(row)

    async def delete_server(self, user_id: str, mcp_id: str) -> bool:
        result = await self._execute("DELETE FROM user_mcp_servers WHERE user_id = $1 AND mcp_id = $2", user_id, mcp_id)
        return _affected_rows(result) > 0

    async def touch_server_used(self, user_id: str, mcp_id: str) -> None:
        await self._execute(
            "UPDATE user_mcp_servers SET last_used_at = now() WHERE user_id = $1 AND mcp_id = $2",
            user_id,
            mcp_id,
        )

    async def count_session_bindings(self, user_id: str, mcp_id: str) -> int:
        rows = await self._fetch(
            "SELECT servers_json FROM enterprise_session_mcp_bindings WHERE user_id = $1",
            user_id,
        )
        return sum(1 for row in rows if _binding_references(_json_records(row["servers_json"]), mcp_id))

    async def list_session_bindings(self, user_id: str, mcp_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch(
            "SELECT project_id, session_id, updated_at, servers_json "
            "FROM enterprise_session_mcp_bindings WHERE user_id = $1",
            user_id,
        )
        return [
            {
                "project_id": str(row["project_id"]),
                "session_id": str(row["session_id"]),
                "updated_at": _iso(row["updated_at"]),
            }
            for row in rows
            if _binding_references(_json_records(row["servers_json"]), mcp_id)
        ]

    async def unbind_server(self, user_id: str, mcp_id: str) -> int:
        """Drop ``mcp_id`` from every binding of ``user_id``; delete emptied rows."""
        rows = await self._fetch(
            "SELECT project_id, session_id, servers_json "
            "FROM enterprise_session_mcp_bindings WHERE user_id = $1",
            user_id,
        )
        changed = 0
        for row in rows:
            servers = _json_records(row["servers_json"])
            remaining = [item for item in servers if str(item.get("mcp_id") or "") != mcp_id]
            if len(remaining) == len(servers):
                continue
            if remaining:
                await self._execute(
                    "UPDATE enterprise_session_mcp_bindings SET servers_json = $1, updated_at = now() "
                    "WHERE project_id = $2 AND session_id = $3 AND user_id = $4",
                    json.dumps(remaining, sort_keys=True),
                    str(row["project_id"]),
                    str(row["session_id"]),
                    user_id,
                )
            else:
                await self._execute(
                    "DELETE FROM enterprise_session_mcp_bindings "
                    "WHERE project_id = $1 AND session_id = $2 AND user_id = $3",
                    str(row["project_id"]),
                    str(row["session_id"]),
                    user_id,
                )
            changed += 1
        return changed

    async def get_session_binding(self, project_id: str, session_id: str, user_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT project_id, session_id, user_id, servers_json, created_at, updated_at
            FROM enterprise_session_mcp_bindings
            WHERE project_id = $1 AND session_id = $2 AND user_id = $3
            """,
            project_id,
            session_id,
            user_id,
        )
        return _binding(row) if row else None

    async def set_session_binding(
        self,
        *,
        project_id: str,
        session_id: str,
        user_id: str,
        servers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized = _normalized_servers(servers)
        existing = await self.get_session_binding(project_id, session_id, user_id)
        # 按 mcp_id/revision 投影比较：旧行未快照 display_name，直接比较整行会把
        # 升级前已绑定的会话误判为 selection locked。
        if existing and _binding_projection(existing["servers"]) != _binding_projection(normalized):
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP selection is locked for this session."
            )
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_session_mcp_bindings (
                project_id, session_id, user_id, servers_json, created_at, updated_at
            ) VALUES ($1, $2, $3, $4::jsonb, now(), now())
            ON CONFLICT(project_id, session_id) DO UPDATE SET updated_at = now()
            WHERE enterprise_session_mcp_bindings.user_id = excluded.user_id
              AND enterprise_session_mcp_bindings.servers_json = excluded.servers_json
            RETURNING project_id, session_id, user_id, servers_json, created_at, updated_at
            """,
            project_id,
            session_id,
            user_id,
            json.dumps(normalized, sort_keys=True),
        )
        if row is None:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP selection is locked for this session."
            )
        return _binding(row)

    async def delete_session_binding(self, project_id: str, session_id: str, user_id: str) -> bool:
        result = await self._execute(
            """
            DELETE FROM enterprise_session_mcp_bindings
            WHERE project_id = $1 AND session_id = $2 AND user_id = $3
            """,
            project_id,
            session_id,
            user_id,
        )
        return _affected_rows(result) > 0

    def _record(self, row: Any) -> dict[str, Any]:
        token = self._codec.decrypt(str(row["token_blob"])) if row["token_blob"] else None
        return {
            "user_id": str(row["user_id"]),
            "id": str(row["mcp_id"]),
            "display_name": str(row["display_name"]),
            "transport": str(row["transport"]),
            "url": str(row["url"]),
            "token": token,
            "token_hint": str(row["token_hint"]) if row["token_hint"] else None,
            "allowed_tools": _json_list(row["allowed_tools_json"]),
            "blocked_tools": _json_list(row["blocked_tools_json"]),
            "enabled": bool(row["enabled"]),
            "revision": int(row["revision"]),
            "last_used_at": _iso(row["last_used_at"]),
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
        }


_SELECT = """
SELECT user_id, mcp_id, display_name, transport, url, token_blob, token_hint,
       allowed_tools_json, blocked_tools_json, enabled, revision, last_used_at, created_at, updated_at
FROM user_mcp_servers
"""


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        loaded = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _normalized_servers(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {key: item[key] for key in ("mcp_id", "revision", "display_name") if key in item}
            for item in servers
        ),
        key=lambda item: item["mcp_id"],
    )


def _binding_projection(servers: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return sorted((str(item.get("mcp_id") or ""), int(item.get("revision") or 0)) for item in servers)


def _binding(row: Any) -> dict[str, Any]:
    return {
        "project_id": str(row["project_id"]),
        "session_id": str(row["session_id"]),
        "user_id": str(row["user_id"]),
        "servers": _json_records(row["servers_json"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _json_records(value: Any) -> list[dict[str, Any]]:
    loaded = value if isinstance(value, list) else json.loads(value or "[]")
    return [dict(item) for item in loaded if isinstance(item, dict)]


def _binding_references(servers: list[dict[str, Any]], mcp_id: str) -> bool:
    return any(str(item.get("mcp_id") or "") == mcp_id for item in servers)


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else str(value) if value is not None else None

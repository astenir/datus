"""Local stores for user-owned MCP servers and session bindings."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.model_credentials import CredentialSecretCodec
from datus_enterprise.personal_mcp import token_hint
from datus_enterprise.storage.local.common import _offload_sqlite_async_methods, _sqlite_now


class InMemoryUserMcpServerStore:
    """Process-local personal MCP store for tests and local mode."""

    def __init__(self) -> None:
        self._servers: dict[tuple[str, str], dict[str, Any]] = {}
        self._bindings: dict[tuple[str, str], dict[str, Any]] = {}

    async def list_servers(self, user_id: str) -> list[dict[str, Any]]:
        records = [_copy_record(record) for (owner, _), record in self._servers.items() if owner == user_id]
        return sorted(records, key=lambda record: (str(record["created_at"]), str(record["id"])))

    async def get_server(self, user_id: str, mcp_id: str) -> dict[str, Any] | None:
        record = self._servers.get((user_id, mcp_id))
        return _copy_record(record) if record else None

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
        now = _sqlite_now()
        existing = self._servers.get((user_id, mcp_id))
        revision = int(existing.get("revision", 0)) + 1 if existing else 1
        record = {
            "user_id": user_id,
            "id": mcp_id,
            "display_name": display_name,
            "transport": transport,
            "url": url,
            "token": token,
            "token_hint": token_hint(token),
            "allowed_tools": list(allowed_tools),
            "blocked_tools": list(blocked_tools),
            "enabled": bool(enabled),
            "revision": revision,
            "last_used_at": existing.get("last_used_at") if existing else None,
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._servers[(user_id, mcp_id)] = record
        return _copy_record(record)

    async def delete_server(self, user_id: str, mcp_id: str) -> bool:
        return self._servers.pop((user_id, mcp_id), None) is not None

    async def touch_server_used(self, user_id: str, mcp_id: str) -> None:
        record = self._servers.get((user_id, mcp_id))
        if record:
            record["last_used_at"] = _sqlite_now()

    async def count_session_bindings(self, user_id: str, mcp_id: str) -> int:
        return sum(
            1
            for binding in self._bindings.values()
            if binding["user_id"] == user_id and _binding_references(binding["servers"], mcp_id)
        )

    async def list_session_bindings(self, user_id: str, mcp_id: str) -> list[dict[str, Any]]:
        return [
            {
                "project_id": str(binding["project_id"]),
                "session_id": str(binding["session_id"]),
                "updated_at": str(binding["updated_at"]),
            }
            for binding in self._bindings.values()
            if binding["user_id"] == user_id and _binding_references(binding["servers"], mcp_id)
        ]

    async def unbind_server(self, user_id: str, mcp_id: str) -> int:
        """Drop ``mcp_id`` from every binding of ``user_id``; remove emptied rows."""
        changed = 0
        for key in list(self._bindings):
            binding = self._bindings[key]
            if binding["user_id"] != user_id:
                continue
            remaining = [item for item in binding["servers"] if str(item.get("mcp_id") or "") != mcp_id]
            if len(remaining) == len(binding["servers"]):
                continue
            if remaining:
                binding["servers"] = remaining
                binding["updated_at"] = _sqlite_now()
            else:
                del self._bindings[key]
            changed += 1
        return changed

    async def get_session_binding(self, project_id: str, session_id: str, user_id: str) -> dict[str, Any] | None:
        record = self._bindings.get((project_id, session_id))
        return dict(record) if record and record["user_id"] == user_id else None

    async def set_session_binding(
        self,
        *,
        project_id: str,
        session_id: str,
        user_id: str,
        servers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        existing = self._bindings.get((project_id, session_id))
        # _binding_record 内部按 mcp_id/revision 投影比较并拒绝变更，这里只校验归属。
        if existing and existing["user_id"] != user_id:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP selection is locked for this session."
            )
        normalized = _binding_record(project_id, session_id, user_id, servers, existing=existing)
        self._bindings[(project_id, session_id)] = normalized
        return dict(normalized)

    async def delete_session_binding(self, project_id: str, session_id: str, user_id: str) -> bool:
        binding = self._bindings.get((project_id, session_id))
        if binding is None or binding["user_id"] != user_id:
            return False
        del self._bindings[(project_id, session_id)]
        return True


@_offload_sqlite_async_methods
class SqliteUserMcpServerStore:
    """SQLite personal MCP store with encrypted bearer tokens."""

    def __init__(self, db_path: str, encryption_secret: str | None = None) -> None:
        self._db_path = db_path
        secret = encryption_secret or os.getenv("DATUS_USER_MCP_SECRET")
        self._codec = CredentialSecretCodec(secret)
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_servers(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"{_SELECT_SERVERS} WHERE user_id = ? ORDER BY created_at, mcp_id", (user_id,)
            ).fetchall()
        return [self._record(row) for row in rows]

    async def get_server(self, user_id: str, mcp_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(f"{_SELECT_SERVERS} WHERE user_id = ? AND mcp_id = ?", (user_id, mcp_id)).fetchone()
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
        token_blob = self._codec.encrypt(token) if token else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_mcp_servers (
                    user_id, mcp_id, display_name, transport, url, token_blob, token_hint,
                    allowed_tools_json, blocked_tools_json, enabled, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    mcp_id,
                    display_name,
                    transport,
                    url,
                    token_blob,
                    token_hint(token),
                    json.dumps(allowed_tools),
                    json.dumps(blocked_tools),
                    1 if enabled else 0,
                ),
            )
            conn.commit()
        record = await self.get_server(user_id, mcp_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist personal MCP server.")
        return record

    async def delete_server(self, user_id: str, mcp_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM user_mcp_servers WHERE user_id = ? AND mcp_id = ?", (user_id, mcp_id))
            conn.commit()
        return cursor.rowcount > 0

    async def touch_server_used(self, user_id: str, mcp_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_mcp_servers SET last_used_at = CURRENT_TIMESTAMP WHERE user_id = ? AND mcp_id = ?",
                (user_id, mcp_id),
            )
            conn.commit()

    async def count_session_bindings(self, user_id: str, mcp_id: str) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT servers_json FROM enterprise_session_mcp_bindings WHERE user_id = ?", (user_id,)
            ).fetchall()
        return sum(1 for row in rows if _binding_references(_json_records(row[0]), mcp_id))

    async def list_session_bindings(self, user_id: str, mcp_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id, session_id, updated_at, servers_json "
                "FROM enterprise_session_mcp_bindings WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [
            {
                "project_id": str(row[0]),
                "session_id": str(row[1]),
                "updated_at": str(row[2]),
            }
            for row in rows
            if _binding_references(_json_records(row[3]), mcp_id)
        ]

    async def unbind_server(self, user_id: str, mcp_id: str) -> int:
        """Drop ``mcp_id`` from every binding of ``user_id``; delete emptied rows."""
        changed = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id, session_id, servers_json FROM enterprise_session_mcp_bindings WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            for row in rows:
                servers = _json_records(row[2])
                remaining = [item for item in servers if str(item.get("mcp_id") or "") != mcp_id]
                if len(remaining) == len(servers):
                    continue
                if remaining:
                    conn.execute(
                        "UPDATE enterprise_session_mcp_bindings SET servers_json = ?, updated_at = CURRENT_TIMESTAMP "
                        "WHERE project_id = ? AND session_id = ? AND user_id = ?",
                        (json.dumps(remaining, sort_keys=True), row[0], row[1], user_id),
                    )
                else:
                    conn.execute(
                        "DELETE FROM enterprise_session_mcp_bindings "
                        "WHERE project_id = ? AND session_id = ? AND user_id = ?",
                        (row[0], row[1], user_id),
                    )
                changed += 1
            conn.commit()
        return changed

    async def get_session_binding(self, project_id: str, session_id: str, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, session_id, user_id, servers_json, created_at, updated_at
                FROM enterprise_session_mcp_bindings
                WHERE project_id = ? AND session_id = ? AND user_id = ?
                """,
                (project_id, session_id, user_id),
            ).fetchone()
        return _binding_from_row(row) if row else None

    async def set_session_binding(
        self,
        *,
        project_id: str,
        session_id: str,
        user_id: str,
        servers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        existing = await self.get_session_binding(project_id, session_id, user_id)
        normalized = _binding_record(project_id, session_id, user_id, servers, existing=existing)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_session_mcp_bindings (
                    project_id, session_id, user_id, servers_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id, session_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (project_id, session_id, user_id, json.dumps(normalized["servers"], sort_keys=True)),
            )
            conn.commit()
        result = await self.get_session_binding(project_id, session_id, user_id)
        if result is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist session MCP binding.")
        return result

    async def delete_session_binding(self, project_id: str, session_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM enterprise_session_mcp_bindings
                WHERE project_id = ? AND session_id = ? AND user_id = ?
                """,
                (project_id, session_id, user_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def _record(self, row: sqlite3.Row) -> dict[str, Any]:
        token = self._codec.decrypt(str(row[5])) if row[5] else None
        return {
            "user_id": str(row[0]),
            "id": str(row[1]),
            "display_name": str(row[2]),
            "transport": str(row[3]),
            "url": str(row[4]),
            "token": token,
            "token_hint": str(row[6]) if row[6] else None,
            "allowed_tools": _json_list(row[7]),
            "blocked_tools": _json_list(row[8]),
            "enabled": bool(row[9]),
            "revision": int(row[10]),
            "last_used_at": str(row[11]) if row[11] else None,
            "created_at": str(row[12]),
            "updated_at": str(row[13]),
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SQLITE_SCHEMA)
            conn.commit()


_SELECT_SERVERS = """
SELECT user_id, mcp_id, display_name, transport, url, token_blob, token_hint,
       allowed_tools_json, blocked_tools_json, enabled, revision, last_used_at, created_at, updated_at
FROM user_mcp_servers
"""

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_mcp_servers (
    user_id TEXT NOT NULL,
    mcp_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    transport TEXT NOT NULL,
    url TEXT NOT NULL,
    token_blob TEXT,
    token_hint TEXT,
    allowed_tools_json TEXT NOT NULL DEFAULT '[]',
    blocked_tools_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    revision INTEGER NOT NULL DEFAULT 1,
    last_used_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, mcp_id)
);
CREATE INDEX IF NOT EXISTS idx_user_mcp_servers_user_enabled
ON user_mcp_servers (user_id, enabled, created_at);
CREATE TABLE IF NOT EXISTS enterprise_session_mcp_bindings (
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    servers_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_session_mcp_bindings_user
ON enterprise_session_mcp_bindings (project_id, user_id, updated_at);
"""


def _copy_record(record: dict[str, Any]) -> dict[str, Any]:
    copied = dict(record)
    copied["allowed_tools"] = list(record.get("allowed_tools") or [])
    copied["blocked_tools"] = list(record.get("blocked_tools") or [])
    return copied


def _binding_record(
    project_id: str,
    session_id: str,
    user_id: str,
    servers: list[dict[str, Any]],
    *,
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _sqlite_now()
    stored = _binding_servers(servers)
    # 比较时只投影 mcp_id/revision：旧行未快照 display_name，直接比较整行会把
    # 升级前已绑定的会话误判为 selection locked。
    if existing and _binding_projection(existing["servers"]) != _binding_projection(stored):
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP selection is locked for this session."
        )
    return {
        "project_id": project_id,
        "session_id": session_id,
        "user_id": user_id,
        "servers": stored,
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
    }


def _binding_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "project_id": str(row[0]),
        "session_id": str(row[1]),
        "user_id": str(row[2]),
        "servers": _json_records(row[3]),
        "created_at": str(row[4]),
        "updated_at": str(row[5]),
    }


def _binding_servers(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalized binding entries; snapshots ``display_name`` when provided."""
    return sorted(
        ({key: item[key] for key in ("mcp_id", "revision", "display_name") if key in item} for item in servers),
        key=lambda item: item["mcp_id"],
    )


def _binding_projection(servers: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return sorted((str(item.get("mcp_id") or ""), int(item.get("revision") or 0)) for item in servers)


def _json_list(value: Any) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _json_records(value: Any) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [dict(item) for item in loaded if isinstance(item, dict)] if isinstance(loaded, list) else []


def _binding_references(servers: list[dict[str, Any]], mcp_id: str) -> bool:
    return any(str(item.get("mcp_id") or "") == mcp_id for item in servers)

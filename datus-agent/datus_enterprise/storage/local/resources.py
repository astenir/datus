"""Local datasource grant, Agent, and session-owner stores."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.local.common import (
    _copy_agent_record,
    _copy_datasource_grant_record,
    _datasource_grant_record_from_row,
    _grant_matches_filters,
    _grant_matches_search,
    _normalized_agent_acl,
    _normalized_agent_record,
    _normalized_agent_status,
    _normalized_grant_effect,
    _normalized_grant_scope,
    _offload_sqlite_async_methods,
    _sqlite_like_contains_pattern,
    _sqlite_now,
)


class InMemoryEnterpriseDatasourceGrantStore:
    """Process-local datasource grant metadata store for tests and local mode."""

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        records = [
            _copy_datasource_grant_record(record)
            for record in self._grants.values()
            if _grant_matches_filters(
                record,
                subject_type=subject_type,
                subject_id=subject_id,
                datasource_key=datasource_key,
            )
        ]
        return sorted(
            records,
            key=lambda record: (
                str(record["subject_type"]),
                str(record["subject_id"]),
                str(record["datasource_key"]),
            ),
        )

    async def list_grants_page(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
        effect: str | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Return a stable, filtered slice without copying every grant."""

        records = sorted(
            (
                record
                for record in self._grants.values()
                if _grant_matches_filters(
                    record,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    datasource_key=datasource_key,
                )
                and (effect is None or str(record.get("effect") or "allow") == effect)
                and _grant_matches_search(record, search)
            ),
            key=lambda record: (
                str(record["subject_type"]),
                str(record["subject_id"]),
                str(record["datasource_key"]),
            ),
        )
        return [_copy_datasource_grant_record(record) for record in records[offset : offset + limit]]

    async def count_grants_by_subjects(
        self,
        *,
        subject_type: str,
        subject_ids: list[str],
    ) -> dict[str, int]:
        subject_id_set = set(subject_ids)
        counts = {subject_id: 0 for subject_id in subject_ids}
        for record in self._grants.values():
            subject_id = str(record.get("subject_id") or "")
            if record.get("subject_type") == subject_type and subject_id in subject_id_set:
                counts[subject_id] += 1
        return counts

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        record = self._grants.get((subject_type, subject_id, datasource_key))
        return _copy_datasource_grant_record(record) if record is not None else None

    async def put_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
        effect: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _sqlite_now()
        key = (subject_type, subject_id, datasource_key)
        existing = self._grants.get(key)
        record = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
            "effect": _normalized_grant_effect(effect),
            "scope": _normalized_grant_scope(scope),
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._grants[key] = record
        return _copy_datasource_grant_record(record)

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        return self._grants.pop((subject_type, subject_id, datasource_key), None) is not None


@_offload_sqlite_async_methods
class SqliteEnterpriseDatasourceGrantStore:
    """SQLite-backed datasource grant metadata store for single-node deployments."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if subject_type is not None:
            where.append("subject_type = ?")
            params.append(subject_type)
        if subject_id is not None:
            where.append("subject_id = ?")
            params.append(subject_id)
        if datasource_key is not None:
            where.append("datasource_key = ?")
            params.append(datasource_key)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        query = f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [_datasource_grant_record_from_row(row) for row in rows]

    async def list_grants_page(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
        effect: str | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("subject_type", subject_type),
            ("subject_id", subject_id),
            ("datasource_key", datasource_key),
            ("effect", effect),
        ):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)
        if search and search.strip():
            pattern = _sqlite_like_contains_pattern(search.strip())
            where.append(
                """(
                    lower(subject_type) LIKE ? ESCAPE '\\'
                    OR lower(subject_id) LIKE ? ESCAPE '\\'
                    OR lower(datasource_key) LIKE ? ESCAPE '\\'
                    OR lower(effect) LIKE ? ESCAPE '\\'
                    OR lower(scope_json) LIKE ? ESCAPE '\\'
                    OR lower(COALESCE(json_extract(scope_json, '$.catalogs'), '')) LIKE ? ESCAPE '\\'
                    OR lower(COALESCE(json_extract(scope_json, '$.databases'), '')) LIKE ? ESCAPE '\\'
                    OR lower(COALESCE(json_extract(scope_json, '$.schemas'), '')) LIKE ? ESCAPE '\\'
                    OR lower(COALESCE(json_extract(scope_json, '$.tables'), '')) LIKE ? ESCAPE '\\'
                )"""
            )
            params.extend([pattern] * 9)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.extend((int(limit), int(offset)))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
                FROM enterprise_datasource_grants
                {where_sql}
                ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        return [_datasource_grant_record_from_row(row) for row in rows]

    async def count_grants_by_subjects(
        self,
        *,
        subject_type: str,
        subject_ids: list[str],
    ) -> dict[str, int]:
        counts = {subject_id: 0 for subject_id in subject_ids}
        if not subject_ids:
            return counts
        placeholders = ", ".join("?" for _ in subject_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT subject_id, COUNT(*)
                FROM enterprise_datasource_grants
                WHERE subject_type = ? AND subject_id IN ({placeholders})
                GROUP BY subject_id
                """,
                (subject_type, *subject_ids),
            ).fetchall()
        for row in rows:
            counts[str(row[0])] = int(row[1])
        return counts

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
                FROM enterprise_datasource_grants
                WHERE subject_type = ? AND subject_id = ? AND datasource_key = ?
                """,
                (subject_type, subject_id, datasource_key),
            ).fetchone()
        return _datasource_grant_record_from_row(row) if row else None

    async def put_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
        effect: str,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_effect = _normalized_grant_effect(effect)
        normalized_scope = _normalized_grant_scope(scope)
        scope_json = json.dumps(normalized_scope, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enterprise_datasource_grants (
                    subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(subject_type, subject_id, datasource_key) DO UPDATE SET
                    effect = excluded.effect,
                    scope_json = excluded.scope_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (subject_type, subject_id, datasource_key, normalized_effect, scope_json),
            )
            conn.commit()
        record = await self.get_grant(
            subject_type=subject_type,
            subject_id=subject_id,
            datasource_key=datasource_key,
        )
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist datasource grant.")
        return record

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM enterprise_datasource_grants
                WHERE subject_type = ? AND subject_id = ? AND datasource_key = ?
                """,
                (subject_type, subject_id, datasource_key),
            )
            conn.commit()
        return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    datasource_key TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    scope_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (subject_type, subject_id, datasource_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enterprise_datasource_grants_datasource
                ON enterprise_datasource_grants (datasource_key, subject_type, subject_id)
                """
            )
            conn.commit()


class InMemoryEnterpriseAgentStore:
    """Process-local enterprise agent registry for tests and single-node local mode."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
        self._prompt_versions: dict[tuple[str, str], dict[str, Any]] = {}
        self._prompt_version_labels: dict[tuple[str, str], str] = {}
        self._active_prompt_versions: dict[str, str] = {}

    async def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        records = [
            _copy_agent_record(record)
            for record in self._agents.values()
            if status is None or record.get("status") == status
        ]
        return sorted(records, key=lambda record: str(record["agent_id"]))

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        record = self._agents.get(agent_id)
        return _copy_agent_record(record) if record is not None else None

    async def put_agent(self, *, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _sqlite_now()
        existing = self._agents.get(agent_id)
        record = _normalized_agent_record(
            {
                **(existing or {}),
                **dict(payload),
                "agent_id": agent_id,
                "created_at": (existing or {}).get("created_at") or now,
                "updated_at": now,
            }
        )
        self._agents[agent_id] = record
        return _copy_agent_record(record)

    async def set_agent_status(self, agent_id: str, status: str) -> dict[str, Any] | None:
        record = self._agents.get(agent_id)
        if record is None:
            return None
        updated = dict(record)
        updated["status"] = _normalized_agent_status(status)
        updated["updated_at"] = _sqlite_now()
        self._agents[agent_id] = _normalized_agent_record(updated)
        return _copy_agent_record(self._agents[agent_id])

    async def put_agent_acl(self, agent_id: str, acl: dict[str, Any]) -> dict[str, Any] | None:
        record = self._agents.get(agent_id)
        if record is None:
            return None
        updated = dict(record)
        updated["acl"] = _normalized_agent_acl(acl)
        updated["updated_at"] = _sqlite_now()
        self._agents[agent_id] = _normalized_agent_record(updated)
        return _copy_agent_record(self._agents[agent_id])

    async def delete_agent(self, agent_id: str) -> bool:
        deleted = self._agents.pop(agent_id, None) is not None
        self._active_prompt_versions.pop(agent_id, None)
        version_ids = [
            version_id for stored_agent_id, version_id in self._prompt_versions if stored_agent_id == agent_id
        ]
        for version_id in version_ids:
            record = self._prompt_versions.pop((agent_id, version_id))
            self._prompt_version_labels.pop((agent_id, str(record["version"])), None)
        return deleted

    async def list_prompt_versions(self, agent_id: str) -> list[dict[str, Any]]:
        from datus.api.enterprise.prompt_versions import copy_prompt_version_record

        active_version_id = self._active_prompt_versions.get(agent_id)
        records = [
            copy_prompt_version_record(record, active=version_id == active_version_id)
            for (stored_agent_id, version_id), record in self._prompt_versions.items()
            if stored_agent_id == agent_id
        ]
        return sorted(
            records, key=lambda record: (str(record.get("created_at") or ""), str(record["version_id"])), reverse=True
        )

    async def get_prompt_version(self, agent_id: str, version_id: str) -> dict[str, Any] | None:
        from datus.api.enterprise.prompt_versions import copy_prompt_version_record

        record = self._prompt_versions.get((agent_id, version_id))
        if record is None:
            return None
        return copy_prompt_version_record(record, active=self._active_prompt_versions.get(agent_id) == version_id)

    async def get_active_prompt_version(self, agent_id: str) -> dict[str, Any] | None:
        version_id = self._active_prompt_versions.get(agent_id)
        return await self.get_prompt_version(agent_id, version_id) if version_id else None

    async def create_prompt_version(
        self,
        *,
        agent_id: str,
        version: str,
        prompt_template: str,
        prompt_language: str,
        change_note: str | None,
        based_on_version_id: str | None,
        created_by: str | None,
    ) -> dict[str, Any]:
        from datus.api.enterprise.prompt_versions import (
            PromptVersionAgentNotFoundError,
            PromptVersionConflictError,
            PromptVersionNotFoundError,
            copy_prompt_version_record,
            normalized_prompt_version_input,
        )

        if agent_id not in self._agents:
            raise PromptVersionAgentNotFoundError("Agent not found.")
        normalized = normalized_prompt_version_input(
            agent_id=agent_id,
            version=version,
            prompt_template=prompt_template,
            prompt_language=prompt_language,
            change_note=change_note,
            based_on_version_id=based_on_version_id,
            created_by=created_by,
        )
        label_key = (agent_id, str(normalized["version"]))
        if label_key in self._prompt_version_labels:
            raise PromptVersionConflictError("Prompt version already exists for this Agent.")
        if based_on_version_id and (agent_id, based_on_version_id) not in self._prompt_versions:
            raise PromptVersionNotFoundError("Base prompt version not found for this Agent.")
        normalized["created_at"] = _sqlite_now()
        version_id = str(normalized["version_id"])
        self._prompt_versions[(agent_id, version_id)] = normalized
        self._prompt_version_labels[label_key] = version_id
        return copy_prompt_version_record(normalized, active=False)

    async def activate_prompt_version(
        self,
        *,
        agent_id: str,
        version_id: str,
        expected_active_version_id: str | None,
        activated_by: str | None,  # noqa: ARG002
    ) -> dict[str, Any]:
        from datus.api.enterprise.prompt_versions import (
            PromptVersionAgentNotFoundError,
            PromptVersionConflictError,
            PromptVersionNotFoundError,
            copy_prompt_version_record,
        )

        agent = self._agents.get(agent_id)
        if agent is None:
            raise PromptVersionAgentNotFoundError("Agent not found.")
        record = self._prompt_versions.get((agent_id, version_id))
        if record is None:
            raise PromptVersionNotFoundError("Prompt version not found for this Agent.")
        current_version_id = self._active_prompt_versions.get(agent_id)
        if current_version_id != expected_active_version_id:
            raise PromptVersionConflictError("The active prompt version changed; reload before activating.")
        self._active_prompt_versions[agent_id] = version_id
        updated = dict(agent)
        updated.update(
            {
                "prompt_template": record["prompt_template"],
                "prompt_language": record["prompt_language"],
                "prompt_version": record["version"],
                "updated_at": _sqlite_now(),
            }
        )
        self._agents[agent_id] = _normalized_agent_record(updated)
        return copy_prompt_version_record(record, active=True)


class InMemorySessionOwnerStore:
    """Process-local session owner store for tests and local mode."""

    def __init__(self) -> None:
        self._owners: dict[tuple[str, str], str] = {}

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        self._owners[(project_id, session_id)] = user_id

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        return self._owners.get((project_id, session_id))

    async def get_session(self, project_id: str, session_id: str) -> dict[str, Any] | None:
        """Return one owner record for admin session details."""

        owner = self._owners.get((project_id, session_id))
        if owner is None:
            return None
        return {
            "project_id": project_id,
            "session_id": session_id,
            "user_id": owner,
            "created_at": None,
            "updated_at": None,
        }

    async def get_sessions(self, project_id: str, session_ids: list[str]) -> list[dict[str, Any]]:
        records = [await self.get_session(project_id, session_id) for session_id in session_ids]
        return [record for record in records if record is not None]

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        self._owners.pop((project_id, session_id), None)

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        return [
            session_id
            for (stored_project, session_id), owner in self._owners.items()
            if stored_project == project_id and owner == user_id
        ]

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return owner metadata for admin session management."""

        records = [
            {
                "project_id": stored_project,
                "session_id": session_id,
                "user_id": owner,
                "created_at": None,
                "updated_at": None,
            }
            for (stored_project, session_id), owner in self._owners.items()
            if stored_project == project_id and (user_id is None or owner == user_id)
        ]
        return sorted(records, key=lambda record: (str(record["user_id"]), str(record["session_id"])))

    async def list_sessions_page(
        self,
        project_id: str,
        user_id: str | None = None,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        records = await self.list_sessions(project_id, user_id)
        return records[offset : offset + limit]


@_offload_sqlite_async_methods
class SqliteSessionOwnerStore:
    """SQLite-backed ``session_owners`` metadata index.

    This is a small default implementation for single-node deployments and
    tests. Enterprise deployments can replace it with Postgres/Redis-backed
    metadata through ``enterprise.session_owner_store.class``.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_owners (project_id, session_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id, session_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (project_id, session_id, user_id),
            )
            conn.commit()

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM session_owners WHERE project_id = ? AND session_id = ?",
                (project_id, session_id),
            ).fetchone()
        return str(row[0]) if row else None

    async def get_session(self, project_id: str, session_id: str) -> dict[str, Any] | None:
        """Return one owner record for admin session details."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ? AND session_id = ?
                """,
                (project_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "project_id": str(row[0]),
            "session_id": str(row[1]),
            "user_id": str(row[2]),
            "created_at": row[3],
            "updated_at": row[4],
        }

    async def get_sessions(self, project_id: str, session_ids: list[str]) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        placeholders = ", ".join("?" for _ in session_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ? AND session_id IN ({placeholders})
                """,
                (project_id, *session_ids),
            ).fetchall()
        return [
            {
                "project_id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM session_owners WHERE project_id = ? AND session_id = ?",
                (project_id, session_id),
            )
            conn.commit()

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id
                FROM session_owners
                WHERE project_id = ? AND user_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id, user_id),
            ).fetchall()
        return [str(row[0]) for row in rows]

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return owner metadata for admin session management."""

        params: tuple[str, ...]
        if user_id is None:
            query = """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """
            params = (project_id,)
        else:
            query = """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = ? AND user_id = ?
                ORDER BY updated_at DESC, session_id ASC
                """
            params = (project_id, user_id)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "project_id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    async def list_sessions_page(
        self,
        project_id: str,
        user_id: str | None = None,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [project_id]
        where = "project_id = ?"
        if user_id is not None:
            where += " AND user_id = ?"
            params.append(user_id)
        params.extend((int(limit), int(offset)))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE {where}
                ORDER BY updated_at DESC, session_id ASC
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
        return [
            {
                "project_id": str(row[0]),
                "session_id": str(row[1]),
                "user_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_owners (
                    project_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_owners_user
                ON session_owners (project_id, user_id, updated_at)
                """
            )
            conn.commit()

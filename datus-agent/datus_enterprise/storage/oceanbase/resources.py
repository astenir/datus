"""OceanBase datasource grant and Agent metadata stores."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from datus.api.enterprise.prompt_versions import (
    PromptVersionAgentNotFoundError,
    PromptVersionConflictError,
    PromptVersionNotFoundError,
    normalized_prompt_version_input,
)
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.common.normalization import (
    _like_contains_pattern,
    _normalized_agent_acl,
    _normalized_agent_metadata,
    _normalized_agent_status,
    _normalized_grant_effect,
    _normalized_grant_scope,
)
from datus_enterprise.storage.oceanbase.base import _ObStoreBase
from datus_enterprise.storage.oceanbase.records import (
    _agent_record,
    _datasource_grant_record,
    _prompt_version_record,
    _where_mysql,
)
from datus_enterprise.storage.oceanbase.schema import _SCHEMA_SQL

_AGENT_COLUMNS = """
agent_id,
name,
description,
node_class,
status,
owner_user_id,
datasource_id,
artifact_slug,
prompt_template,
prompt_language,
prompt_version,
tools_json,
mcp_json,
skills_json,
scoped_context_json,
rules_json,
max_turns,
acl_json,
created_at,
updated_at
"""


class ObEnterpriseDatasourceGrantStore(_ObStoreBase):
    """OceanBase MySQL-backed datasource grant metadata store."""

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _where_mysql(
            {"subject_type": subject_type, "subject_id": subject_id, "datasource_key": datasource_key}
        )
        rows = await self._fetchall(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """,
            tuple(params),
        )
        return [_datasource_grant_record(row) for row in rows]

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
        filters: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("subject_type", subject_type),
            ("subject_id", subject_id),
            ("datasource_key", datasource_key),
            ("effect", effect),
        ):
            if value is not None:
                filters.append(f"{column} = %s")
                params.append(value)
        if search and search.strip():
            pattern = _like_contains_pattern(search.strip().casefold())
            filters.append(
                """(
                    lower(subject_type) LIKE %s ESCAPE '\\\\'
                    OR lower(subject_id) LIKE %s ESCAPE '\\\\'
                    OR lower(datasource_key) LIKE %s ESCAPE '\\\\'
                    OR lower(effect) LIKE %s ESCAPE '\\\\'
                    OR lower(scope_json) LIKE %s ESCAPE '\\\\'
                )"""
            )
            params.extend([pattern] * 5)
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend((int(limit), int(offset)))
        rows = await self._fetchall(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        return [_datasource_grant_record(row) for row in rows]

    async def count_grants_by_subjects(
        self,
        *,
        subject_type: str,
        subject_ids: list[str],
    ) -> dict[str, int]:
        counts = {subject_id: 0 for subject_id in subject_ids}
        if not subject_ids:
            return counts
        placeholders = ", ".join("%s" for _ in subject_ids)
        rows = await self._fetchall(
            f"""
            SELECT subject_id, COUNT(*) AS grant_count
            FROM enterprise_datasource_grants
            WHERE subject_type = %s AND subject_id IN ({placeholders})
            GROUP BY subject_id
            """,
            (subject_type, *subject_ids),
        )
        for row in rows:
            counts[str(row["subject_id"])] = int(row["grant_count"])
        return counts

    async def get_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            WHERE subject_type = %s AND subject_id = %s AND datasource_key = %s
            """,
            (subject_type, subject_id, datasource_key),
        )
        return _datasource_grant_record(row) if row else None

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
        await self._execute(
            """
            INSERT INTO enterprise_datasource_grants (
                subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                effect = VALUES(effect),
                scope_json = VALUES(scope_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                subject_type,
                subject_id,
                datasource_key,
                normalized_effect,
                json.dumps(normalized_scope, sort_keys=True, separators=(",", ":")),
            ),
        )
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
        count = await self._execute(
            """
            DELETE FROM enterprise_datasource_grants
            WHERE subject_type = %s AND subject_id = %s AND datasource_key = %s
            """,
            (subject_type, subject_id, datasource_key),
        )
        return count > 0


class ObEnterpriseAgentStore(_ObStoreBase):
    """OceanBase MySQL-backed enterprise custom agent metadata store."""

    async def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = await self._fetchall(f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents ORDER BY agent_id ASC")
        else:
            rows = await self._fetchall(
                f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents WHERE status = %s ORDER BY agent_id ASC",
                (_normalized_agent_status(status),),
            )
        return [_agent_record(row) for row in rows]

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            f"SELECT {_AGENT_COLUMNS} FROM enterprise_agents WHERE agent_id = %s",
            (agent_id,),
        )
        return _agent_record(row) if row else None

    async def put_agent(self, *, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalized_agent_metadata({"agent_id": agent_id, **dict(payload)})
        await self._execute(
            """
            INSERT INTO enterprise_agents (
                agent_id, name, description, node_class, status, owner_user_id, datasource_id, artifact_slug,
                prompt_template, prompt_language, prompt_version, tools_json, mcp_json, skills_json,
                scoped_context_json, rules_json, max_turns, acl_json, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                description = VALUES(description),
                node_class = VALUES(node_class),
                status = VALUES(status),
                owner_user_id = VALUES(owner_user_id),
                datasource_id = VALUES(datasource_id),
                artifact_slug = VALUES(artifact_slug),
                prompt_template = VALUES(prompt_template),
                prompt_language = VALUES(prompt_language),
                prompt_version = VALUES(prompt_version),
                tools_json = VALUES(tools_json),
                mcp_json = VALUES(mcp_json),
                skills_json = VALUES(skills_json),
                scoped_context_json = VALUES(scoped_context_json),
                rules_json = VALUES(rules_json),
                max_turns = VALUES(max_turns),
                acl_json = VALUES(acl_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                normalized["agent_id"],
                normalized["name"],
                normalized["description"],
                normalized["node_class"],
                normalized["status"],
                normalized["owner_user_id"],
                normalized["datasource_id"],
                normalized["artifact_slug"],
                normalized["prompt_template"],
                normalized["prompt_language"],
                normalized["prompt_version"],
                json.dumps(normalized["tools"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["mcp"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["skills"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["scoped_context"], ensure_ascii=False, sort_keys=True),
                json.dumps(normalized["rules"], ensure_ascii=False, sort_keys=True),
                normalized["max_turns"],
                json.dumps(normalized["acl"], ensure_ascii=False, sort_keys=True),
            ),
        )
        record = await self.get_agent(normalized["agent_id"])
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise agent.")
        return record

    async def set_agent_status(self, agent_id: str, status: str) -> dict[str, Any] | None:
        await self._execute(
            "UPDATE enterprise_agents SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE agent_id = %s",
            (_normalized_agent_status(status), agent_id),
        )
        return await self.get_agent(agent_id)

    async def put_agent_acl(self, agent_id: str, acl: dict[str, Any]) -> dict[str, Any] | None:
        await self._execute(
            "UPDATE enterprise_agents SET acl_json = %s, updated_at = CURRENT_TIMESTAMP WHERE agent_id = %s",
            (json.dumps(_normalized_agent_acl(acl), ensure_ascii=False, sort_keys=True), agent_id),
        )
        return await self.get_agent(agent_id)

    async def delete_agent(self, agent_id: str) -> bool:
        return await asyncio.to_thread(self._delete_agent_sync, agent_id)

    def _delete_agent_sync(self, agent_id: str) -> bool:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM enterprise_agent_active_prompt_versions WHERE agent_id = %s", (agent_id,))
                cursor.execute("DELETE FROM enterprise_agent_prompt_versions WHERE agent_id = %s", (agent_id,))
                cursor.execute("DELETE FROM enterprise_agents WHERE agent_id = %s", (agent_id,))
                return int(cursor.rowcount or 0) > 0

    async def list_prompt_versions(self, agent_id: str) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT
                version.version_id,
                version.agent_id,
                version.version_label,
                version.prompt_template,
                version.prompt_language,
                version.content_sha256,
                version.change_note,
                version.based_on_version_id,
                version.created_by,
                version.created_at,
                active.version_id IS NOT NULL AS active
            FROM enterprise_agent_prompt_versions AS version
            LEFT JOIN enterprise_agent_active_prompt_versions AS active
                ON active.agent_id = version.agent_id AND active.version_id = version.version_id
            WHERE version.agent_id = %s
            ORDER BY version.created_at DESC, version.version_id DESC
            """,
            (agent_id,),
        )
        return [_prompt_version_record(row) for row in rows]

    async def get_prompt_version(self, agent_id: str, version_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT
                version.version_id,
                version.agent_id,
                version.version_label,
                version.prompt_template,
                version.prompt_language,
                version.content_sha256,
                version.change_note,
                version.based_on_version_id,
                version.created_by,
                version.created_at,
                active.version_id IS NOT NULL AS active
            FROM enterprise_agent_prompt_versions AS version
            LEFT JOIN enterprise_agent_active_prompt_versions AS active
                ON active.agent_id = version.agent_id AND active.version_id = version.version_id
            WHERE version.agent_id = %s AND version.version_id = %s
            """,
            (agent_id, version_id),
        )
        return _prompt_version_record(row) if row else None

    async def get_active_prompt_version(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT
                version.version_id,
                version.agent_id,
                version.version_label,
                version.prompt_template,
                version.prompt_language,
                version.content_sha256,
                version.change_note,
                version.based_on_version_id,
                version.created_by,
                version.created_at,
                1 AS active
            FROM enterprise_agent_active_prompt_versions AS active
            JOIN enterprise_agent_prompt_versions AS version
                ON version.agent_id = active.agent_id AND version.version_id = active.version_id
            WHERE active.agent_id = %s
            """,
            (agent_id,),
        )
        return _prompt_version_record(row) if row else None

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
        normalized = normalized_prompt_version_input(
            agent_id=agent_id,
            version=version,
            prompt_template=prompt_template,
            prompt_language=prompt_language,
            change_note=change_note,
            based_on_version_id=based_on_version_id,
            created_by=created_by,
        )
        if await self.get_agent(agent_id) is None:
            raise PromptVersionAgentNotFoundError("Agent not found.")
        if based_on_version_id and await self.get_prompt_version(agent_id, based_on_version_id) is None:
            raise PromptVersionNotFoundError("Base prompt version not found for this Agent.")
        try:
            await self._execute(
                """
                INSERT INTO enterprise_agent_prompt_versions (
                    version_id,
                    agent_id,
                    version_label,
                    prompt_template,
                    prompt_language,
                    content_sha256,
                    change_note,
                    based_on_version_id,
                    created_by,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (
                    normalized["version_id"],
                    normalized["agent_id"],
                    normalized["version"],
                    normalized["prompt_template"],
                    normalized["prompt_language"],
                    normalized["content_sha256"],
                    normalized["change_note"],
                    normalized["based_on_version_id"],
                    normalized["created_by"],
                ),
            )
        except Exception as exc:
            existing = next(
                (
                    item
                    for item in await self.list_prompt_versions(agent_id)
                    if item["version"] == normalized["version"]
                ),
                None,
            )
            if existing is not None:
                raise PromptVersionConflictError("Prompt version already exists for this Agent.") from exc
            raise
        record = await self.get_prompt_version(agent_id, str(normalized["version_id"]))
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist Agent prompt version.")
        return record

    async def activate_prompt_version(
        self,
        *,
        agent_id: str,
        version_id: str,
        expected_active_version_id: str | None,
        activated_by: str | None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._activate_prompt_version_sync,
            agent_id,
            version_id,
            expected_active_version_id,
            activated_by,
        )

    def _activate_prompt_version_sync(
        self,
        agent_id: str,
        version_id: str,
        expected_active_version_id: str | None,
        activated_by: str | None,
    ) -> dict[str, Any]:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT agent_id FROM enterprise_agents WHERE agent_id = %s FOR UPDATE", (agent_id,))
                if cursor.fetchone() is None:
                    raise PromptVersionAgentNotFoundError("Agent not found.")
                cursor.execute(
                    """
                    SELECT
                        version_id,
                        agent_id,
                        version_label,
                        prompt_template,
                        prompt_language,
                        content_sha256,
                        change_note,
                        based_on_version_id,
                        created_by,
                        created_at,
                        1 AS active
                    FROM enterprise_agent_prompt_versions
                    WHERE agent_id = %s AND version_id = %s
                    """,
                    (agent_id, version_id),
                )
                version = cursor.fetchone()
                if version is None:
                    raise PromptVersionNotFoundError("Prompt version not found for this Agent.")
                cursor.execute(
                    "SELECT version_id FROM enterprise_agent_active_prompt_versions WHERE agent_id = %s FOR UPDATE",
                    (agent_id,),
                )
                current = cursor.fetchone()
                current_version_id = str(current["version_id"]) if current else None
                if current_version_id != expected_active_version_id:
                    raise PromptVersionConflictError("The active prompt version changed; reload before activating.")
                cursor.execute(
                    """
                    INSERT INTO enterprise_agent_active_prompt_versions (
                        agent_id, version_id, activated_by, activated_at
                    )
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        version_id = VALUES(version_id),
                        activated_by = VALUES(activated_by),
                        activated_at = CURRENT_TIMESTAMP
                    """,
                    (agent_id, version_id, activated_by),
                )
                cursor.execute(
                    """
                    UPDATE enterprise_agents
                    SET
                        prompt_template = %s,
                        prompt_language = %s,
                        prompt_version = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = %s
                    """,
                    (
                        version["prompt_template"],
                        version["prompt_language"],
                        version["version_label"],
                        agent_id,
                    ),
                )
        return _prompt_version_record(version)

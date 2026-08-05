"""PostgreSQL datasource grant and Agent metadata stores."""

from __future__ import annotations

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
from datus_enterprise.storage.postgres.base import _PgStoreBase
from datus_enterprise.storage.postgres.records import (
    _affected_rows,
    _agent_record,
    _datasource_grant_record,
    _prompt_version_record,
    _where,
)


class PgEnterpriseDatasourceGrantStore(_PgStoreBase):
    """PostgreSQL-backed datasource grant metadata store."""

    async def list_grants(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        datasource_key: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "datasource_key": datasource_key,
        }
        where_sql, params = _where(filters)
        rows = await self._fetch(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            """,
            *params,
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
                params.append(value)
                filters.append(f"{column} = ${len(params)}")
        if search and search.strip():
            params.append(_like_contains_pattern(search.strip()))
            placeholder = f"${len(params)}"
            filters.append(
                f"""(
                    subject_type ILIKE {placeholder} ESCAPE '\\'
                    OR subject_id ILIKE {placeholder} ESCAPE '\\'
                    OR datasource_key ILIKE {placeholder} ESCAPE '\\'
                    OR effect ILIKE {placeholder} ESCAPE '\\'
                    OR scope_json::text ILIKE {placeholder} ESCAPE '\\'
                )"""
            )
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.extend((int(limit), int(offset)))
        rows = await self._fetch(
            f"""
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            {where_sql}
            ORDER BY subject_type ASC, subject_id ASC, datasource_key ASC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
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
        rows = await self._fetch(
            """
            SELECT subject_id, COUNT(*) AS grant_count
            FROM enterprise_datasource_grants
            WHERE subject_type = $1 AND subject_id = ANY($2::text[])
            GROUP BY subject_id
            """,
            subject_type,
            subject_ids,
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
        row = await self._fetchrow(
            """
            SELECT subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            FROM enterprise_datasource_grants
            WHERE subject_type = $1 AND subject_id = $2 AND datasource_key = $3
            """,
            subject_type,
            subject_id,
            datasource_key,
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
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_datasource_grants (
                subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, now(), now())
            ON CONFLICT(subject_type, subject_id, datasource_key) DO UPDATE SET
                effect = excluded.effect,
                scope_json = excluded.scope_json,
                updated_at = now()
            RETURNING subject_type, subject_id, datasource_key, effect, scope_json, created_at, updated_at
            """,
            subject_type,
            subject_id,
            datasource_key,
            normalized_effect,
            json.dumps(normalized_scope, sort_keys=True, separators=(",", ":")),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist datasource grant.")
        return _datasource_grant_record(row)

    async def delete_grant(
        self,
        *,
        subject_type: str,
        subject_id: str,
        datasource_key: str,
    ) -> bool:
        result = await self._execute(
            """
            DELETE FROM enterprise_datasource_grants
            WHERE subject_type = $1 AND subject_id = $2 AND datasource_key = $3
            """,
            subject_type,
            subject_id,
            datasource_key,
        )
        return _affected_rows(result) > 0


class PgEnterpriseAgentStore(_PgStoreBase):
    """PostgreSQL-backed enterprise custom agent metadata store."""

    async def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = await self._fetch(
                """
                SELECT
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
                    tools,
                    mcp,
                    skills,
                    scoped_context_json,
                    rules,
                    max_turns,
                    acl_json,
                    created_at,
                    updated_at
                FROM enterprise_agents
                ORDER BY agent_id ASC
                """
            )
        else:
            normalized_status = _normalized_agent_status(status)
            rows = await self._fetch(
                """
                SELECT
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
                    tools,
                    mcp,
                    skills,
                    scoped_context_json,
                    rules,
                    max_turns,
                    acl_json,
                    created_at,
                    updated_at
                FROM enterprise_agents
                WHERE status = $1
                ORDER BY agent_id ASC
                """,
                normalized_status,
            )
        return [_agent_record(row) for row in rows]

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT
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
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            FROM enterprise_agents
            WHERE agent_id = $1
            """,
            agent_id,
        )
        return _agent_record(row) if row else None

    async def put_agent(self, *, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalized_agent_metadata({"agent_id": agent_id, **dict(payload)})
        row = await self._fetchrow(
            """
            INSERT INTO enterprise_agents (
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
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12::text[],
                $13::text[],
                $14::text[],
                $15::jsonb,
                $16::text[],
                $17,
                $18::jsonb,
                now(),
                now()
            )
            ON CONFLICT(agent_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                node_class = excluded.node_class,
                status = excluded.status,
                owner_user_id = excluded.owner_user_id,
                datasource_id = excluded.datasource_id,
                artifact_slug = excluded.artifact_slug,
                prompt_template = excluded.prompt_template,
                prompt_language = excluded.prompt_language,
                prompt_version = excluded.prompt_version,
                tools = excluded.tools,
                mcp = excluded.mcp,
                skills = excluded.skills,
                scoped_context_json = excluded.scoped_context_json,
                rules = excluded.rules,
                max_turns = excluded.max_turns,
                acl_json = excluded.acl_json,
                updated_at = now()
            RETURNING
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
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
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
            normalized["tools"],
            normalized["mcp"],
            normalized["skills"],
            json.dumps(normalized["scoped_context"], ensure_ascii=False, sort_keys=True),
            normalized["rules"],
            normalized["max_turns"],
            json.dumps(normalized["acl"], ensure_ascii=False, sort_keys=True),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist enterprise agent.")
        return _agent_record(row)

    async def set_agent_status(self, agent_id: str, status: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            UPDATE enterprise_agents
            SET status = $2, updated_at = now()
            WHERE agent_id = $1
            RETURNING
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
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
            agent_id,
            _normalized_agent_status(status),
        )
        return _agent_record(row) if row else None

    async def put_agent_acl(self, agent_id: str, acl: dict[str, Any]) -> dict[str, Any] | None:
        normalized_acl = _normalized_agent_acl(acl)
        row = await self._fetchrow(
            """
            UPDATE enterprise_agents
            SET acl_json = $2::jsonb, updated_at = now()
            WHERE agent_id = $1
            RETURNING
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
                tools,
                mcp,
                skills,
                scoped_context_json,
                rules,
                max_turns,
                acl_json,
                created_at,
                updated_at
            """,
            agent_id,
            json.dumps(normalized_acl, ensure_ascii=False, sort_keys=True),
        )
        return _agent_record(row) if row else None

    async def delete_agent(self, agent_id: str) -> bool:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute("DELETE FROM enterprise_agent_active_prompt_versions WHERE agent_id = $1", agent_id)
            await conn.execute("DELETE FROM enterprise_agent_prompt_versions WHERE agent_id = $1", agent_id)
            result = await conn.execute("DELETE FROM enterprise_agents WHERE agent_id = $1", agent_id)
        return _affected_rows(result) > 0

    async def list_prompt_versions(self, agent_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch(
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
            WHERE version.agent_id = $1
            ORDER BY version.created_at DESC, version.version_id DESC
            """,
            agent_id,
        )
        return [_prompt_version_record(row) for row in rows]

    async def get_prompt_version(self, agent_id: str, version_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
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
            WHERE version.agent_id = $1 AND version.version_id = $2
            """,
            agent_id,
            version_id,
        )
        return _prompt_version_record(row) if row else None

    async def get_active_prompt_version(self, agent_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
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
                true AS active
            FROM enterprise_agent_active_prompt_versions AS active
            JOIN enterprise_agent_prompt_versions AS version
                ON version.agent_id = active.agent_id AND version.version_id = active.version_id
            WHERE active.agent_id = $1
            """,
            agent_id,
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
            row = await self._fetchrow(
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
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                RETURNING
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
                    false AS active
                """,
                normalized["version_id"],
                normalized["agent_id"],
                normalized["version"],
                normalized["prompt_template"],
                normalized["prompt_language"],
                normalized["content_sha256"],
                normalized["change_note"],
                normalized["based_on_version_id"],
                normalized["created_by"],
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
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist Agent prompt version.")
        return _prompt_version_record(row)

    async def activate_prompt_version(
        self,
        *,
        agent_id: str,
        version_id: str,
        expected_active_version_id: str | None,
        activated_by: str | None,
    ) -> dict[str, Any]:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn, conn.transaction():
            agent = await conn.fetchrow(
                "SELECT agent_id FROM enterprise_agents WHERE agent_id = $1 FOR UPDATE", agent_id
            )
            if agent is None:
                raise PromptVersionAgentNotFoundError("Agent not found.")
            version = await conn.fetchrow(
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
                    true AS active
                FROM enterprise_agent_prompt_versions
                WHERE agent_id = $1 AND version_id = $2
                """,
                agent_id,
                version_id,
            )
            if version is None:
                raise PromptVersionNotFoundError("Prompt version not found for this Agent.")
            current = await conn.fetchrow(
                "SELECT version_id FROM enterprise_agent_active_prompt_versions WHERE agent_id = $1 FOR UPDATE",
                agent_id,
            )
            current_version_id = str(current["version_id"]) if current else None
            if current_version_id != expected_active_version_id:
                raise PromptVersionConflictError("The active prompt version changed; reload before activating.")
            await conn.execute(
                """
                INSERT INTO enterprise_agent_active_prompt_versions (
                    agent_id, version_id, activated_by, activated_at
                )
                VALUES ($1, $2, $3, now())
                ON CONFLICT(agent_id) DO UPDATE SET
                    version_id = excluded.version_id,
                    activated_by = excluded.activated_by,
                    activated_at = now()
                """,
                agent_id,
                version_id,
                activated_by,
            )
            await conn.execute(
                """
                UPDATE enterprise_agents
                SET
                    prompt_template = $2,
                    prompt_language = $3,
                    prompt_version = $4,
                    updated_at = now()
                WHERE agent_id = $1
                """,
                agent_id,
                version["prompt_template"],
                version["prompt_language"],
                version["version_label"],
            )
        return _prompt_version_record(version)

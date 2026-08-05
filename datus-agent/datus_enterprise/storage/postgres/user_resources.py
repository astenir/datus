"""PostgreSQL current-user credential and datasource metadata stores."""

from __future__ import annotations

import os
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.model_credentials import CredentialSecretCodec, api_key_hint
from datus_enterprise.personal_datasources import password_hint
from datus_enterprise.storage.postgres.base import _PgStoreBase
from datus_enterprise.storage.postgres.records import (
    _affected_rows,
    _empty_model_preference,
    _model_credential_record,
    _model_preference_record,
    _user_datasource_record,
)


class PgUserModelCredentialStore(_PgStoreBase):
    """PostgreSQL-backed per-user model credential store."""

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
        secret = encryption_secret or os.getenv("DATUS_USER_MODEL_CREDENTIAL_SECRET")
        self._codec = CredentialSecretCodec(secret)

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = $1
            ORDER BY created_at ASC, credential_id ASC
            """,
            user_id,
        )
        return [_model_credential_record(row, self._codec) for row in rows]

    async def get_credential(self, user_id: str, credential_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = $1 AND credential_id = $2
            """,
            user_id,
            credential_id,
        )
        return _model_credential_record(row, self._codec) if row else None

    async def put_credential(
        self,
        *,
        user_id: str,
        credential_id: str,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO user_model_credentials (
                user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                base_url, display_name, enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now(), now())
            ON CONFLICT(user_id, credential_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                api_key_blob = excluded.api_key_blob,
                api_key_hint = excluded.api_key_hint,
                base_url = excluded.base_url,
                display_name = excluded.display_name,
                enabled = excluded.enabled,
                updated_at = now()
            RETURNING user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                      base_url, display_name, enabled, last_used_at, created_at, updated_at
            """,
            user_id,
            credential_id,
            provider,
            model,
            self._codec.encrypt(api_key),
            api_key_hint(api_key),
            base_url,
            display_name,
            bool(enabled),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist model credential.")
        return _model_credential_record(row, self._codec)

    async def set_credential_enabled(
        self,
        user_id: str,
        credential_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            UPDATE user_model_credentials
            SET enabled = $3, updated_at = now()
            WHERE user_id = $1 AND credential_id = $2
            RETURNING user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                      base_url, display_name, enabled, last_used_at, created_at, updated_at
            """,
            user_id,
            credential_id,
            bool(enabled),
        )
        return _model_credential_record(row, self._codec) if row else None

    async def delete_credential(self, user_id: str, credential_id: str) -> bool:
        result = await self._execute(
            "DELETE FROM user_model_credentials WHERE user_id = $1 AND credential_id = $2",
            user_id,
            credential_id,
        )
        await self._execute(
            """
            UPDATE user_model_preferences
            SET default_credential_id = NULL, default_model = NULL, updated_at = now()
            WHERE user_id = $1 AND default_credential_id = $2
            """,
            user_id,
            credential_id,
        )
        return _affected_rows(result) > 0

    async def get_preference(self, user_id: str) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            SELECT user_id, default_credential_id, default_model, created_at, updated_at
            FROM user_model_preferences
            WHERE user_id = $1
            """,
            user_id,
        )
        return _model_preference_record(row) if row else _empty_model_preference(user_id)

    async def put_preference(
        self,
        *,
        user_id: str,
        default_credential_id: str | None,
        default_model: str | None,
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO user_model_preferences (
                user_id, default_credential_id, default_model, created_at, updated_at
            )
            VALUES ($1, $2, $3, now(), now())
            ON CONFLICT(user_id) DO UPDATE SET
                default_credential_id = excluded.default_credential_id,
                default_model = excluded.default_model,
                updated_at = now()
            RETURNING user_id, default_credential_id, default_model, created_at, updated_at
            """,
            user_id,
            default_credential_id,
            default_model,
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist model preference.")
        return _model_preference_record(row)

    async def touch_credential_used(self, user_id: str, credential_id: str) -> None:
        await self._execute(
            """
            UPDATE user_model_credentials
            SET last_used_at = now()
            WHERE user_id = $1 AND credential_id = $2
            """,
            user_id,
            credential_id,
        )


class PgUserDatasourceStore(_PgStoreBase):
    """PostgreSQL-backed per-user private datasource store."""

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
        secret = encryption_secret or os.getenv("DATUS_USER_DATASOURCE_SECRET")
        self._datasource_codec = CredentialSecretCodec(secret)

    async def list_datasources(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = $1
            ORDER BY created_at ASC, datasource_id ASC
            """,
            user_id,
        )
        return [_user_datasource_record(row, self._datasource_codec) for row in rows]

    async def get_datasource(self, user_id: str, datasource_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = $1 AND datasource_id = $2
            """,
            user_id,
            datasource_id,
        )
        return _user_datasource_record(row, self._datasource_codec) if row else None

    async def put_datasource(
        self,
        *,
        user_id: str,
        datasource_id: str,
        datasource_type: str,
        host: str,
        port: str,
        username: str,
        password: str,
        database: str,
        display_name: str | None = None,
        schema: str | None = None,
        catalog: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO user_datasources (
                user_id, datasource_id, datasource_type, host, port, username, password_blob,
                password_hint, database_name, schema_name, catalog_name, display_name,
                enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, now(), now())
            ON CONFLICT(user_id, datasource_id) DO UPDATE SET
                datasource_type = excluded.datasource_type,
                host = excluded.host,
                port = excluded.port,
                username = excluded.username,
                password_blob = excluded.password_blob,
                password_hint = excluded.password_hint,
                database_name = excluded.database_name,
                schema_name = excluded.schema_name,
                catalog_name = excluded.catalog_name,
                display_name = excluded.display_name,
                enabled = excluded.enabled,
                updated_at = now()
            RETURNING user_id, datasource_id, datasource_type, host, port, username, password_blob,
                      password_hint, database_name, schema_name, catalog_name, display_name,
                      enabled, last_used_at, created_at, updated_at
            """,
            user_id,
            datasource_id,
            datasource_type,
            host,
            port,
            username,
            self._datasource_codec.encrypt(password),
            password_hint(password),
            database,
            schema,
            catalog,
            display_name,
            bool(enabled),
        )
        if row is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist personal datasource.")
        return _user_datasource_record(row, self._datasource_codec)

    async def set_datasource_enabled(
        self,
        user_id: str,
        datasource_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            UPDATE user_datasources
            SET enabled = $3, updated_at = now()
            WHERE user_id = $1 AND datasource_id = $2
            RETURNING user_id, datasource_id, datasource_type, host, port, username, password_blob,
                      password_hint, database_name, schema_name, catalog_name, display_name,
                      enabled, last_used_at, created_at, updated_at
            """,
            user_id,
            datasource_id,
            bool(enabled),
        )
        return _user_datasource_record(row, self._datasource_codec) if row else None

    async def delete_datasource(self, user_id: str, datasource_id: str) -> bool:
        result = await self._execute(
            "DELETE FROM user_datasources WHERE user_id = $1 AND datasource_id = $2",
            user_id,
            datasource_id,
        )
        return _affected_rows(result) > 0

    async def touch_datasource_used(self, user_id: str, datasource_id: str) -> None:
        await self._execute(
            """
            UPDATE user_datasources
            SET last_used_at = now()
            WHERE user_id = $1 AND datasource_id = $2
            """,
            user_id,
            datasource_id,
        )

"""OceanBase current-user credential and datasource metadata stores."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.model_credentials import CredentialSecretCodec, api_key_hint
from datus_enterprise.personal_datasources import password_hint
from datus_enterprise.storage.oceanbase.base import _ObStoreBase
from datus_enterprise.storage.oceanbase.records import (
    _empty_model_preference,
    _model_credential_record,
    _model_preference_record,
    _user_datasource_record,
)
from datus_enterprise.storage.oceanbase.schema import _SCHEMA_SQL


class ObUserModelCredentialStore(_ObStoreBase):
    """OceanBase MySQL-backed per-user model credential store."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
        encryption_secret: str | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        secret = encryption_secret or os.getenv("DATUS_USER_MODEL_CREDENTIAL_SECRET")
        self._codec = CredentialSecretCodec(secret)
        self._user_model_credential_schema_ready = False

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        await self._ensure_user_model_credential_columns()
        rows = await self._fetchall(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = %s
            ORDER BY created_at ASC, credential_id ASC
            """,
            (user_id,),
        )
        return [_model_credential_record(row, self._codec) for row in rows]

    async def get_credential(self, user_id: str, credential_id: str) -> dict[str, Any] | None:
        await self._ensure_user_model_credential_columns()
        row = await self._fetchone(
            """
            SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                   base_url, display_name, enabled, last_used_at, created_at, updated_at
            FROM user_model_credentials
            WHERE user_id = %s AND credential_id = %s
            """,
            (user_id, credential_id),
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
        await self._ensure_user_model_credential_columns()
        await self._execute(
            """
            INSERT INTO user_model_credentials (
                user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                base_url, display_name, enabled, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                provider = VALUES(provider),
                model = VALUES(model),
                api_key_blob = VALUES(api_key_blob),
                api_key_hint = VALUES(api_key_hint),
                base_url = VALUES(base_url),
                display_name = VALUES(display_name),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                credential_id,
                provider,
                model,
                self._codec.encrypt(api_key),
                api_key_hint(api_key),
                base_url,
                display_name,
                bool(enabled),
            ),
        )
        record = await self.get_credential(user_id, credential_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist model credential.")
        return record

    async def _ensure_user_model_credential_columns(self) -> None:
        await asyncio.to_thread(self._ensure_user_model_credential_columns_sync)

    def _ensure_user_model_credential_columns_sync(self) -> None:
        if self._user_model_credential_schema_ready:
            return
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._schema_lock:
            if self._user_model_credential_schema_ready:
                return
            with self._pool.connection(database=self._config.database) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SHOW COLUMNS FROM user_model_credentials LIKE %s", ("base_url",))
                    if cursor.fetchone() is None:
                        cursor.execute("ALTER TABLE user_model_credentials ADD COLUMN base_url VARCHAR(512)")
            self._user_model_credential_schema_ready = True

    async def set_credential_enabled(
        self,
        user_id: str,
        credential_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        updated = await self._execute(
            """
            UPDATE user_model_credentials
            SET enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND credential_id = %s
            """,
            (bool(enabled), user_id, credential_id),
        )
        if updated == 0:
            return None
        return await self.get_credential(user_id, credential_id)

    async def delete_credential(self, user_id: str, credential_id: str) -> bool:
        deleted = await self._execute(
            "DELETE FROM user_model_credentials WHERE user_id = %s AND credential_id = %s",
            (user_id, credential_id),
        )
        await self._execute(
            """
            UPDATE user_model_preferences
            SET default_credential_id = NULL, default_model = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND default_credential_id = %s
            """,
            (user_id, credential_id),
        )
        return deleted > 0

    async def get_preference(self, user_id: str) -> dict[str, Any]:
        row = await self._fetchone(
            """
            SELECT user_id, default_credential_id, default_model, created_at, updated_at
            FROM user_model_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return _model_preference_record(row) if row else _empty_model_preference(user_id)

    async def put_preference(
        self,
        *,
        user_id: str,
        default_credential_id: str | None,
        default_model: str | None,
    ) -> dict[str, Any]:
        await self._execute(
            """
            INSERT INTO user_model_preferences (
                user_id, default_credential_id, default_model, created_at, updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                default_credential_id = VALUES(default_credential_id),
                default_model = VALUES(default_model),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, default_credential_id, default_model),
        )
        return await self.get_preference(user_id)

    async def touch_credential_used(self, user_id: str, credential_id: str) -> None:
        await self._execute(
            """
            UPDATE user_model_credentials
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND credential_id = %s
            """,
            (user_id, credential_id),
        )


class ObUserDatasourceStore(_ObStoreBase):
    """OceanBase MySQL-backed per-user private datasource store."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
        encryption_secret: str | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        secret = encryption_secret or os.getenv("DATUS_USER_DATASOURCE_SECRET")
        self._datasource_codec = CredentialSecretCodec(secret)

    async def list_datasources(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = %s
            ORDER BY created_at ASC, datasource_id ASC
            """,
            (user_id,),
        )
        return [_user_datasource_record(row, self._datasource_codec) for row in rows]

    async def get_datasource(self, user_id: str, datasource_id: str) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                   password_hint, database_name, schema_name, catalog_name, display_name,
                   enabled, last_used_at, created_at, updated_at
            FROM user_datasources
            WHERE user_id = %s AND datasource_id = %s
            """,
            (user_id, datasource_id),
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
        await self._execute(
            """
            INSERT INTO user_datasources (
                user_id, datasource_id, datasource_type, host, port, username, password_blob,
                password_hint, database_name, schema_name, catalog_name, display_name,
                enabled, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                datasource_type = VALUES(datasource_type),
                host = VALUES(host),
                port = VALUES(port),
                username = VALUES(username),
                password_blob = VALUES(password_blob),
                password_hint = VALUES(password_hint),
                database_name = VALUES(database_name),
                schema_name = VALUES(schema_name),
                catalog_name = VALUES(catalog_name),
                display_name = VALUES(display_name),
                enabled = VALUES(enabled),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
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
            ),
        )
        record = await self.get_datasource(user_id, datasource_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist personal datasource.")
        return record

    async def set_datasource_enabled(
        self,
        user_id: str,
        datasource_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        updated = await self._execute(
            """
            UPDATE user_datasources
            SET enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND datasource_id = %s
            """,
            (bool(enabled), user_id, datasource_id),
        )
        if updated == 0:
            return None
        return await self.get_datasource(user_id, datasource_id)

    async def delete_datasource(self, user_id: str, datasource_id: str) -> bool:
        return (
            await self._execute(
                "DELETE FROM user_datasources WHERE user_id = %s AND datasource_id = %s",
                (user_id, datasource_id),
            )
            > 0
        )

    async def touch_datasource_used(self, user_id: str, datasource_id: str) -> None:
        await self._execute(
            """
            UPDATE user_datasources
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND datasource_id = %s
            """,
            (user_id, datasource_id),
        )

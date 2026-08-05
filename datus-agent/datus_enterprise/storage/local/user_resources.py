"""Local user model-credential and datasource stores."""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.model_credentials import CredentialSecretCodec
from datus_enterprise.personal_datasources import password_hint
from datus_enterprise.storage.local.common import (
    _api_key_hint,
    _copy_model_credential_record,
    _copy_user_datasource_record,
    _empty_model_preference,
    _ensure_sqlite_columns,
    _model_preference_from_row,
    _offload_sqlite_async_methods,
    _sqlite_now,
)


class InMemoryUserModelCredentialStore:
    """Process-local user model credential store for tests and local mode."""

    def __init__(self) -> None:
        self._credentials: dict[tuple[str, str], dict[str, Any]] = {}
        self._preferences: dict[str, dict[str, Any]] = {}

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        records = [
            _copy_model_credential_record(record)
            for (owner, _), record in self._credentials.items()
            if owner == user_id
        ]
        return sorted(records, key=lambda record: str(record["created_at"]))

    async def get_credential(self, user_id: str, credential_id: str) -> dict[str, Any] | None:
        record = self._credentials.get((user_id, credential_id))
        return _copy_model_credential_record(record) if record is not None else None

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
        now = _sqlite_now()
        existing = self._credentials.get((user_id, credential_id))
        record = {
            "user_id": user_id,
            "id": credential_id,
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "ref_hint": _api_key_hint(api_key),
            "display_name": display_name,
            "enabled": bool(enabled),
            "last_used_at": existing.get("last_used_at") if existing else None,
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._credentials[(user_id, credential_id)] = record
        return _copy_model_credential_record(record)

    async def set_credential_enabled(
        self,
        user_id: str,
        credential_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        record = self._credentials.get((user_id, credential_id))
        if record is None:
            return None
        updated = dict(record)
        updated["enabled"] = bool(enabled)
        updated["updated_at"] = _sqlite_now()
        self._credentials[(user_id, credential_id)] = updated
        return _copy_model_credential_record(updated)

    async def delete_credential(self, user_id: str, credential_id: str) -> bool:
        deleted = self._credentials.pop((user_id, credential_id), None) is not None
        preference = self._preferences.get(user_id)
        if preference and preference.get("default_credential_id") == credential_id:
            await self.put_preference(user_id=user_id, default_credential_id=None, default_model=None)
        return deleted

    async def get_preference(self, user_id: str) -> dict[str, Any]:
        record = self._preferences.get(user_id)
        if record is not None:
            return dict(record)
        return _empty_model_preference(user_id)

    async def put_preference(
        self,
        *,
        user_id: str,
        default_credential_id: str | None,
        default_model: str | None,
    ) -> dict[str, Any]:
        now = _sqlite_now()
        existing = self._preferences.get(user_id)
        record = {
            "user_id": user_id,
            "default_credential_id": default_credential_id,
            "default_model": default_model,
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._preferences[user_id] = record
        return dict(record)

    async def touch_credential_used(self, user_id: str, credential_id: str) -> None:
        record = self._credentials.get((user_id, credential_id))
        if record is None:
            return
        updated = dict(record)
        updated["last_used_at"] = _sqlite_now()
        self._credentials[(user_id, credential_id)] = updated


@_offload_sqlite_async_methods
class SqliteUserModelCredentialStore:
    """SQLite-backed user model credential store for single-node deployments.

    API keys are stored as encrypted blobs using a server-side secret. Set
    ``DATUS_USER_MODEL_CREDENTIAL_SECRET`` or pass ``encryption_secret`` in
    ``agent.enterprise.user_model_credential_store.kwargs``.
    """

    def __init__(self, db_path: str, encryption_secret: str | None = None) -> None:
        self._db_path = db_path
        secret = encryption_secret or os.getenv("DATUS_USER_MODEL_CREDENTIAL_SECRET")
        self._codec = CredentialSecretCodec(secret)
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_credentials(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                       base_url, display_name, enabled, last_used_at, created_at, updated_at
                FROM user_model_credentials
                WHERE user_id = ?
                ORDER BY created_at ASC, credential_id ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    async def get_credential(self, user_id: str, credential_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                       base_url, display_name, enabled, last_used_at, created_at, updated_at
                FROM user_model_credentials
                WHERE user_id = ? AND credential_id = ?
                """,
                (user_id, credential_id),
            ).fetchone()
        return self._record_from_row(row) if row else None

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
        api_key_blob = self._codec.encrypt(api_key)
        api_key_hint = _api_key_hint(api_key)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_model_credentials (
                    user_id, credential_id, provider, model, api_key_blob, api_key_hint,
                    base_url, display_name, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, credential_id) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    api_key_blob = excluded.api_key_blob,
                    api_key_hint = excluded.api_key_hint,
                    base_url = excluded.base_url,
                    display_name = excluded.display_name,
                    enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    credential_id,
                    provider,
                    model,
                    api_key_blob,
                    api_key_hint,
                    base_url,
                    display_name,
                    1 if enabled else 0,
                ),
            )
            conn.commit()
        record = await self.get_credential(user_id, credential_id)
        if record is None:
            raise DatusException(ErrorCode.COMMON_UNKNOWN, message="Failed to persist model credential.")
        return record

    async def set_credential_enabled(
        self,
        user_id: str,
        credential_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE user_model_credentials
                SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND credential_id = ?
                """,
                (1 if enabled else 0, user_id, credential_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_credential(user_id, credential_id)

    async def delete_credential(self, user_id: str, credential_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_model_credentials WHERE user_id = ? AND credential_id = ?",
                (user_id, credential_id),
            )
            conn.execute(
                """
                UPDATE user_model_preferences
                SET default_credential_id = NULL, default_model = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND default_credential_id = ?
                """,
                (user_id, credential_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    async def get_preference(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, default_credential_id, default_model, created_at, updated_at
                FROM user_model_preferences
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return _model_preference_from_row(row) if row else _empty_model_preference(user_id)

    async def put_preference(
        self,
        *,
        user_id: str,
        default_credential_id: str | None,
        default_model: str | None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_model_preferences (
                    user_id, default_credential_id, default_model, created_at, updated_at
                )
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    default_credential_id = excluded.default_credential_id,
                    default_model = excluded.default_model,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, default_credential_id, default_model),
            )
            conn.commit()
        return await self.get_preference(user_id)

    async def touch_credential_used(self, user_id: str, credential_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE user_model_credentials
                SET last_used_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND credential_id = ?
                """,
                (user_id, credential_id),
            )
            conn.commit()

    def _record_from_row(self, row) -> dict[str, Any]:
        return {
            "user_id": str(row["user_id"]),
            "id": str(row["credential_id"]),
            "provider": str(row["provider"]),
            "model": str(row["model"]),
            "api_key": self._codec.decrypt(str(row["api_key_blob"])),
            "base_url": row["base_url"],
            "ref_hint": str(row["api_key_hint"]),
            "display_name": row["display_name"],
            "enabled": bool(row["enabled"]),
            "last_used_at": row["last_used_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_model_credentials (
                    user_id TEXT NOT NULL,
                    credential_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key_blob TEXT NOT NULL,
                    api_key_hint TEXT NOT NULL,
                    base_url TEXT,
                    display_name TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, credential_id)
                )
                """
            )
            _ensure_sqlite_columns(conn, "user_model_credentials", {"base_url": "TEXT"})
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_model_preferences (
                    user_id TEXT PRIMARY KEY,
                    default_credential_id TEXT,
                    default_model TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()


class InMemoryUserDatasourceStore:
    """Process-local private datasource store for tests and local mode."""

    def __init__(self) -> None:
        self._datasources: dict[tuple[str, str], dict[str, Any]] = {}

    async def list_datasources(self, user_id: str) -> list[dict[str, Any]]:
        records = [
            _copy_user_datasource_record(record) for (owner, _), record in self._datasources.items() if owner == user_id
        ]
        return sorted(records, key=lambda record: str(record["created_at"]))

    async def get_datasource(self, user_id: str, datasource_id: str) -> dict[str, Any] | None:
        record = self._datasources.get((user_id, datasource_id))
        return _copy_user_datasource_record(record) if record is not None else None

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
        now = _sqlite_now()
        existing = self._datasources.get((user_id, datasource_id))
        record = {
            "user_id": user_id,
            "id": datasource_id,
            "type": datasource_type,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "password_hint": password_hint(password),
            "database": database,
            "schema": schema,
            "catalog": catalog,
            "display_name": display_name,
            "enabled": bool(enabled),
            "last_used_at": existing.get("last_used_at") if existing else None,
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
        }
        self._datasources[(user_id, datasource_id)] = record
        return _copy_user_datasource_record(record)

    async def set_datasource_enabled(
        self,
        user_id: str,
        datasource_id: str,
        enabled: bool,
    ) -> dict[str, Any] | None:
        record = self._datasources.get((user_id, datasource_id))
        if record is None:
            return None
        updated = dict(record)
        updated["enabled"] = bool(enabled)
        updated["updated_at"] = _sqlite_now()
        self._datasources[(user_id, datasource_id)] = updated
        return _copy_user_datasource_record(updated)

    async def delete_datasource(self, user_id: str, datasource_id: str) -> bool:
        return self._datasources.pop((user_id, datasource_id), None) is not None

    async def touch_datasource_used(self, user_id: str, datasource_id: str) -> None:
        record = self._datasources.get((user_id, datasource_id))
        if record is None:
            return
        updated = dict(record)
        updated["last_used_at"] = _sqlite_now()
        self._datasources[(user_id, datasource_id)] = updated


@_offload_sqlite_async_methods
class SqliteUserDatasourceStore:
    """SQLite-backed user private datasource store for single-node deployments.

    Passwords are stored as encrypted blobs using a server-side secret. Set
    ``DATUS_USER_DATASOURCE_SECRET`` or pass ``encryption_secret`` in
    ``agent.enterprise.user_datasource_store.kwargs``.
    """

    def __init__(self, db_path: str, encryption_secret: str | None = None) -> None:
        self._db_path = db_path
        secret = encryption_secret or os.getenv("DATUS_USER_DATASOURCE_SECRET")
        self._codec = CredentialSecretCodec(secret)
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    async def list_datasources(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                       password_hint, database_name, schema_name, catalog_name, display_name, enabled,
                       last_used_at, created_at, updated_at
                FROM user_datasources
                WHERE user_id = ?
                ORDER BY created_at ASC, datasource_id ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    async def get_datasource(self, user_id: str, datasource_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, datasource_id, datasource_type, host, port, username, password_blob,
                       password_hint, database_name, schema_name, catalog_name, display_name, enabled,
                       last_used_at, created_at, updated_at
                FROM user_datasources
                WHERE user_id = ? AND datasource_id = ?
                """,
                (user_id, datasource_id),
            ).fetchone()
        return self._record_from_row(row) if row else None

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
        password_blob = self._codec.encrypt(password)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_datasources (
                    user_id, datasource_id, datasource_type, host, port, username, password_blob,
                    password_hint, database_name, schema_name, catalog_name, display_name, enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    datasource_id,
                    datasource_type,
                    host,
                    port,
                    username,
                    password_blob,
                    password_hint(password),
                    database,
                    schema,
                    catalog,
                    display_name,
                    1 if enabled else 0,
                ),
            )
            conn.commit()
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
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE user_datasources
                SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND datasource_id = ?
                """,
                (1 if enabled else 0, user_id, datasource_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_datasource(user_id, datasource_id)

    async def delete_datasource(self, user_id: str, datasource_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_datasources WHERE user_id = ? AND datasource_id = ?",
                (user_id, datasource_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    async def touch_datasource_used(self, user_id: str, datasource_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE user_datasources
                SET last_used_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND datasource_id = ?
                """,
                (user_id, datasource_id),
            )
            conn.commit()

    def _record_from_row(self, row) -> dict[str, Any]:
        return {
            "user_id": str(row["user_id"]),
            "id": str(row["datasource_id"]),
            "type": str(row["datasource_type"]),
            "host": str(row["host"]),
            "port": str(row["port"]),
            "username": str(row["username"]),
            "password": self._codec.decrypt(str(row["password_blob"])),
            "password_hint": str(row["password_hint"]),
            "database": str(row["database_name"]),
            "schema": row["schema_name"],
            "catalog": row["catalog_name"],
            "display_name": row["display_name"],
            "enabled": bool(row["enabled"]),
            "last_used_at": row["last_used_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_datasources (
                    user_id TEXT NOT NULL,
                    datasource_id TEXT NOT NULL,
                    datasource_type TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password_blob TEXT NOT NULL,
                    password_hint TEXT NOT NULL,
                    database_name TEXT NOT NULL,
                    schema_name TEXT,
                    catalog_name TEXT,
                    display_name TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, datasource_id)
                )
                """
            )
            conn.commit()

#!/usr/bin/env python3
"""Re-encrypt credentials written by the legacy Compose missing-value keys."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
from dataclasses import dataclass

import asyncpg
from cryptography.fernet import Fernet, InvalidToken

_LEGACY_MODEL_SECRET = "<MISSING:DATUS_USER_MODEL_CREDENTIAL_SECRET>"
_LEGACY_DATASOURCE_SECRET = "<MISSING:DATUS_USER_DATASOURCE_SECRET>"


@dataclass(frozen=True)
class _TableSpec:
    table: str
    id_column: str
    blob_column: str
    legacy_secret: str


_TABLES = (
    _TableSpec("user_model_credentials", "credential_id", "api_key_blob", _LEGACY_MODEL_SECRET),
    _TableSpec("user_datasources", "datasource_id", "password_blob", _LEGACY_DATASOURCE_SECRET),
)


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _reencrypt_blob(blob: str, *, legacy_secret: str, new_secret: str) -> tuple[str, bool]:
    encoded = blob.encode("ascii")
    new_codec = _fernet(new_secret)
    try:
        new_codec.decrypt(encoded)
        return blob, False
    except InvalidToken:
        pass

    try:
        plaintext = _fernet(legacy_secret).decrypt(encoded)
    except InvalidToken as exc:
        raise RuntimeError("credential blob cannot be decrypted with the current or legacy Compose key") from exc
    return new_codec.encrypt(plaintext).decode("ascii"), True


async def _migrate_table(conn: asyncpg.Connection, spec: _TableSpec, new_secret: str) -> int:
    if await conn.fetchval("SELECT to_regclass($1)", f"public.{spec.table}") is None:
        return 0

    rows = await conn.fetch(
        f"SELECT user_id, {spec.id_column}, {spec.blob_column} FROM {spec.table} FOR UPDATE"  # noqa: S608
    )
    migrated = 0
    for row in rows:
        blob, changed = _reencrypt_blob(
            str(row[spec.blob_column]),
            legacy_secret=spec.legacy_secret,
            new_secret=new_secret,
        )
        if not changed:
            continue
        await conn.execute(
            f"UPDATE {spec.table} SET {spec.blob_column} = $1 WHERE user_id = $2 AND {spec.id_column} = $3",  # noqa: S608
            blob,
            row["user_id"],
            row[spec.id_column],
        )
        migrated += 1
    return migrated


async def _run() -> None:
    dsn = os.environ["DATUS_ENTERPRISE_PG_DSN"]
    secrets = {
        "user_model_credentials": os.environ["DATUS_USER_MODEL_CREDENTIAL_SECRET"],
        "user_datasources": os.environ["DATUS_USER_DATASOURCE_SECRET"],
    }
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            for spec in _TABLES:
                migrated = await _migrate_table(conn, spec, secrets[spec.table])
                if migrated:
                    print(f"Migrated {migrated} legacy encrypted record(s) in {spec.table}.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_run())

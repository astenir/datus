import importlib.util
import sys
from pathlib import Path

import pytest

from datus_enterprise.model_credentials import CredentialSecretCodec

SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "migrate_compose_credential_secrets.py"
SPEC = importlib.util.spec_from_file_location("migrate_compose_credential_secrets", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
migration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migration
SPEC.loader.exec_module(migration)

NEW_SECRET = "new-compose-credential-encryption-secret-32"


def test_reencrypt_blob_migrates_legacy_placeholder_key():
    legacy_codec = migration._fernet(migration._LEGACY_MODEL_SECRET)
    legacy_blob = legacy_codec.encrypt(b"secret-value").decode("ascii")

    migrated_blob, changed = migration._reencrypt_blob(
        legacy_blob,
        legacy_secret=migration._LEGACY_MODEL_SECRET,
        new_secret=NEW_SECRET,
    )

    assert changed is True
    assert CredentialSecretCodec(NEW_SECRET).decrypt(migrated_blob) == "secret-value"


def test_reencrypt_blob_keeps_current_key_unchanged():
    current_blob = CredentialSecretCodec(NEW_SECRET).encrypt("secret-value")

    migrated_blob, changed = migration._reencrypt_blob(
        current_blob,
        legacy_secret=migration._LEGACY_MODEL_SECRET,
        new_secret=NEW_SECRET,
    )

    assert changed is False
    assert migrated_blob == current_blob


def test_reencrypt_blob_rejects_unknown_key_without_modifying_data():
    unknown_blob = CredentialSecretCodec("unrelated-encryption-secret-value-32").encrypt("secret-value")

    with pytest.raises(RuntimeError, match="cannot be decrypted"):
        migration._reencrypt_blob(
            unknown_blob,
            legacy_secret=migration._LEGACY_MODEL_SECRET,
            new_secret=NEW_SECRET,
        )

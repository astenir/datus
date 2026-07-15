import pytest

from datus.utils.exceptions import DatusException
from datus_enterprise.model_credentials import CredentialSecretCodec


@pytest.mark.parametrize(
    "secret",
    [
        None,
        "too-short",
        "<MISSING:DATUS_USER_MODEL_CREDENTIAL_SECRET>",
        "<MISSING:DATUS_USER_DATASOURCE_SECRET>",
    ],
)
def test_credential_secret_codec_rejects_missing_or_invalid_secret(secret):
    with pytest.raises(DatusException, match="must be explicitly configured"):
        CredentialSecretCodec(secret)


def test_credential_secret_codec_round_trips_with_explicit_secret():
    codec = CredentialSecretCodec("test-credential-encryption-secret-32")

    encrypted = codec.encrypt("sensitive-value")

    assert encrypted != "sensitive-value"
    assert codec.decrypt(encrypted) == "sensitive-value"

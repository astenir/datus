"""Downstream enterprise auth-provider loader coverage."""

import pytest

from datus.api.auth.loader import load_auth_provider
from datus.utils.exceptions import DatusException


def test_enterprise_enabled_requires_custom_auth_provider():
    with pytest.raises(DatusException, match="NoAuthProvider is local-only"):
        load_auth_provider({}, datasource="default", enterprise_config={"enabled": True})


def test_enterprise_enabled_rejects_explicit_no_auth_provider():
    with pytest.raises(DatusException, match="cannot use NoAuthProvider"):
        load_auth_provider(
            {"auth_provider": {"class": "datus.api.auth.no_auth_provider.NoAuthProvider"}},
            datasource="default",
            enterprise_config={"enabled": True},
        )


def test_enterprise_enabled_loads_signed_header_provider():
    provider = load_auth_provider(
        {
            "auth_provider": {
                "class": "datus_enterprise.auth_provider.SignedHeaderAuthProvider",
                "kwargs": {"secret": "test-secret"},
            }
        },
        datasource="default",
        enterprise_config={"enabled": True},
    )

    assert provider.__class__.__name__ == "SignedHeaderAuthProvider"


def test_enterprise_enabled_loads_userinfo_bearer_provider():
    provider = load_auth_provider(
        {
            "auth_provider": {
                "class": "datus_enterprise.auth_provider.UserInfoBearerAuthProvider",
                "kwargs": {"userinfo_url": "https://sso.example.internal/api/userinfo"},
            }
        },
        datasource="default",
        enterprise_config={"enabled": True},
    )

    assert provider.__class__.__name__ == "UserInfoBearerAuthProvider"

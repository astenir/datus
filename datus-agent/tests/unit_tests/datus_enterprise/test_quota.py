import pytest

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseQuotaStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus_enterprise.quota import consume_enterprise_quota


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


def _install_extensions(monkeypatch, *, quota_store=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=FailingAuditSink(),
            quota_store=quota_store,
        ),
    )


@pytest.mark.asyncio
async def test_quota_store_unavailable_returns_error_when_audit_fails(monkeypatch):
    _install_extensions(monkeypatch, quota_store=None)
    ctx = AppContext(user_id="alice")

    result = await consume_enterprise_quota(
        ctx,
        resource="chat.stream",
        resource_type="chat",
    )

    assert result.success is False
    assert result.errorCode == "QUOTA_STORE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_quota_exceeded_returns_error_when_audit_fails(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    await quota_store.put_quota(
        subject_type="user",
        subject_id="alice",
        resource="chat.stream",
        limit=1,
        window_seconds=3600,
    )
    await quota_store.consume_quota(
        subjects=[{"subject_type": "user", "subject_id": "alice"}],
        resource="chat.stream",
    )
    _install_extensions(monkeypatch, quota_store=quota_store)
    ctx = AppContext(user_id="alice")

    result = await consume_enterprise_quota(
        ctx,
        resource="chat.stream",
        resource_type="chat",
    )

    assert result.success is False
    assert result.errorCode == "QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_quota_allow_consumes_usage_when_audit_fails(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    await quota_store.put_quota(
        subject_type="user",
        subject_id="alice",
        resource="chat.stream",
        limit=2,
        window_seconds=3600,
    )
    _install_extensions(monkeypatch, quota_store=quota_store)
    ctx = AppContext(user_id="alice")

    result = await consume_enterprise_quota(
        ctx,
        resource="chat.stream",
        resource_type="chat",
    )

    usage = await quota_store.list_usage(subject_type="user", subject_id="alice", resource="chat.stream")
    assert result is None
    assert usage[0]["used"] == 1

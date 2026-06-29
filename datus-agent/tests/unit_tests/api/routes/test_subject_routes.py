# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for enterprise-safe subject tree route."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import InMemorySessionOwnerStore, LocalAuthorizationProvider, NoopAuditSink
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.explorer_models import CreateDirectoryInput, SubjectListData
from datus.api.routes import subject_routes
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


def _enterprise_extensions() -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=DatasourceGrantConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=NoopAuditSink(),
    )


def _svc(*, current_datasource: str = "hr") -> MagicMock:
    svc = MagicMock()
    svc.agent_config = SimpleNamespace(
        services=SimpleNamespace(
            datasources={
                "finance": SimpleNamespace(type="sqlite"),
                "hr": SimpleNamespace(type="sqlite"),
            },
            default_datasource=None,
        ),
        current_datasource=current_datasource,
        principal={},
    )
    return svc


@pytest.mark.asyncio
async def test_subject_tree_uses_projected_config_without_mutating_cached_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    captured_configs = []

    class FakeExplorerService:
        def __init__(self, agent_config):
            captured_configs.append(agent_config)

        async def get_subject_list(self):
            return Result(success=True, data=SubjectListData(subjects=[]))

    monkeypatch.setattr(subject_routes, "ExplorerService", FakeExplorerService)
    svc = _svc(current_datasource="hr")
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    result = await subject_routes.list_subject_tree(svc, ctx, datasource_id="")

    assert result.success is True
    assert len(captured_configs) == 1
    assert captured_configs[0].current_datasource == "finance"
    assert set(captured_configs[0].services.datasources) == {"finance"}
    assert svc.agent_config.current_datasource == "hr"
    assert set(svc.agent_config.services.datasources) == {"finance", "hr"}


@pytest.mark.asyncio
async def test_subject_tree_mutation_uses_projected_config(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    captured_configs = []
    captured_requests = []

    class FakeExplorerService:
        def __init__(self, agent_config):
            captured_configs.append(agent_config)

        async def create_directory(self, request):
            captured_requests.append(request)
            return Result(success=True, data={"created": True})

    monkeypatch.setattr(subject_routes, "ExplorerService", FakeExplorerService)
    svc = _svc(current_datasource="hr")
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.config.edit"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    result = await subject_routes.create_directory(
        CreateDirectoryInput(subject_path=["finance"]),
        svc,
        ctx,
        datasource_id="finance",
    )

    assert result.success is True
    assert captured_configs[0].current_datasource == "finance"
    assert set(captured_configs[0].services.datasources) == {"finance"}
    assert captured_requests[0].subject_path == ["finance"]
    assert svc.agent_config.current_datasource == "hr"


@pytest.mark.asyncio
async def test_subject_tree_rejects_unauthorized_requested_datasource(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())

    class RejectExplorerService:
        def __init__(self, agent_config):
            raise AssertionError("unauthorized subject tree request initialized ExplorerService")

    monkeypatch.setattr(subject_routes, "ExplorerService", RejectExplorerService)
    svc = _svc(current_datasource="finance")
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    with pytest.raises(HTTPException) as exc:
        await subject_routes.list_subject_tree(svc, ctx, datasource_id="hr")

    assert exc.value.status_code == 403
    assert "not authorized" in str(exc.value.detail)

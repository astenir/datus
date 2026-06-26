from types import SimpleNamespace

import pytest

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import ProjectionInput
from datus.utils.exceptions import DatusException
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


def _agent_config(*, current_datasource: str = "finance"):
    return SimpleNamespace(
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


@pytest.mark.asyncio
async def test_datasource_grant_projector_filters_clone_and_injects_principal():
    base_config = _agent_config()
    ctx = AppContext(
        user_id="alice",
        principal={"department": "finance"},
        datasource_grants={
            "finance": {"effect": "allow", "allow_sql": True, "tables": ["fnd_*"]},
            "hr": {"effect": "deny"},
        },
    )

    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=ctx,
            base_config=base_config,
            operation="chat.stream",
            requested_datasource="finance",
        )
    )

    assert set(result.config.services.datasources) == {"finance"}
    assert set(base_config.services.datasources) == {"finance", "hr"}
    assert result.config is not base_config
    assert result.config.current_datasource == "finance"
    assert result.principal["user_id"] == "alice"
    assert result.principal["datasource"] == "finance"
    assert result.principal["allowed_datasources"] == ["finance"]
    assert result.principal["datasource_grants"]["finance"]["tables"] == ["fnd_*"]


@pytest.mark.asyncio
async def test_datasource_grant_projector_denies_requested_datasource_without_grant():
    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(datasource_grants={"finance": {"effect": "allow"}}),
            base_config=_agent_config(),
            operation="chat.stream",
            requested_datasource="hr",
        )
    )

    assert result.denied_reason == "Datasource 'hr' is not authorized for this request."


@pytest.mark.asyncio
async def test_datasource_grant_projector_denies_when_operation_flag_disallows_sql():
    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(datasource_grants={"finance": {"effect": "allow", "allow_sql": False}}),
            base_config=_agent_config(),
            operation="chat.stream",
            requested_datasource="finance",
        )
    )

    assert result.denied_reason == "No datasource grant available."


@pytest.mark.asyncio
async def test_datasource_grant_projector_denies_requested_schema_outside_scope():
    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(datasource_grants={"finance": {"effect": "allow", "schemas": ["mart"]}}),
            base_config=_agent_config(),
            operation="catalog.list",
            requested_datasource="finance",
            requested_schema="private",
        )
    )

    assert result.denied_reason == "Requested schema 'private' is not authorized for datasource 'finance'."


@pytest.mark.asyncio
async def test_datasource_grant_projector_selects_authorized_default_without_mutating_base():
    base_config = _agent_config(current_datasource="hr")

    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(datasource_grants={"finance": True}),
            base_config=base_config,
            operation="chat.stream",
        )
    )

    assert result.denied_reason is None
    assert result.config.current_datasource == "finance"
    assert base_config.current_datasource == "hr"


@pytest.mark.asyncio
async def test_datasource_grant_projector_rejects_unknown_requested_datasource():
    with pytest.raises(DatusException):
        await DatasourceGrantConfigProjector().project(
            ProjectionInput(
                ctx=AppContext(datasource_grants={"finance": True}),
                base_config=_agent_config(),
                operation="chat.stream",
                requested_datasource="missing",
            )
        )

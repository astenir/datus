import pytest

from datus.api.enterprise.defaults import InMemoryEnterpriseAgentStore
from datus_enterprise.oceanbase_stores import _SCHEMA_SQL as OB_SCHEMA_SQL
from datus_enterprise.postgres_stores import _SCHEMA_SQL as PG_SCHEMA_SQL


def test_prompt_version_metadata_schemas_are_additive_and_unique_per_agent_label():
    pg = " ".join(PG_SCHEMA_SQL.lower().split())
    ob = " ".join(OB_SCHEMA_SQL.lower().split())

    assert "create table if not exists enterprise_agent_prompt_versions" in pg
    assert "create table if not exists enterprise_agent_active_prompt_versions" in pg
    assert "unique (agent_id, version_label)" in pg
    assert "create table if not exists enterprise_agent_prompt_versions" in ob
    assert "create table if not exists enterprise_agent_active_prompt_versions" in ob
    assert "unique key uq_enterprise_agent_prompt_version_label (agent_id, version_label)" in ob
    assert "drop table enterprise_agent_prompt_versions" not in pg
    assert "drop table enterprise_agent_prompt_versions" not in ob


@pytest.mark.asyncio
async def test_in_memory_agent_delete_removes_prompt_versions_and_active_reference():
    store = InMemoryEnterpriseAgentStore()
    await store.put_agent(
        agent_id="analyst",
        payload={
            "name": "Analyst",
            "node_class": "gen_sql",
            "prompt_template": "Prompt v1",
            "prompt_version": "1.0",
        },
    )
    version = await store.create_prompt_version(
        agent_id="analyst",
        version="1.0",
        prompt_template="Prompt v1",
        prompt_language="en",
        change_note=None,
        based_on_version_id=None,
        created_by="operator",
    )
    await store.activate_prompt_version(
        agent_id="analyst",
        version_id=version["version_id"],
        expected_active_version_id=None,
        activated_by="operator",
    )

    assert await store.delete_agent("analyst") is True
    assert await store.list_prompt_versions("analyst") == []
    assert await store.get_active_prompt_version("analyst") is None

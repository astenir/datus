"""Typed local-compatible wrapper for upstream legacy Agent routes."""

from fastapi import APIRouter, Query

from datus.api.deps import ServiceDep
from datus.api.models.agent_models import CreateAgentInput, EditAgentInput
from datus.api.models.base_models import Result
from datus.api.models.downstream import (
    AgentListData,
    AgentMutationData,
    AgentToolsData,
    AgentUseToolsData,
    GetAgentData,
)
from datus.api.routes import agent_routes as upstream_agent_routes

router = APIRouter(prefix="/api/v1", tags=["agent"])


@router.get(
    "/agent/use_tools",
    response_model=Result[AgentUseToolsData],
    summary="Get Agent Available Tools",
    description="Get available tool types for a given sub-agent type",
)
async def get_agent_use_tools(
    agent_type: str = Query(..., description="Agent type: 'gen_sql' or 'gen_report'"),
) -> Result[AgentUseToolsData]:
    return await upstream_agent_routes.get_agent_use_tools(agent_type)


@router.get(
    "/agent",
    response_model=Result[GetAgentData],
    summary="Get Agent Detail",
    description="Get configuration details for a specific agent by id",
)
async def get_agent(
    svc: ServiceDep,
    agent_id: str = Query(..., description="Agent id"),
) -> Result[GetAgentData]:
    return await upstream_agent_routes.get_agent(svc, agent_id)


@router.get(
    "/agent/list",
    response_model=Result[AgentListData],
    summary="List Agents",
    description="Get list of all available agents (builtin + custom sub-agents)",
)
async def list_agents(svc: ServiceDep) -> Result[AgentListData]:
    return await upstream_agent_routes.list_agents(svc)


@router.post(
    "/agent/create",
    response_model=Result[AgentMutationData],
    summary="Create Agent",
    description="Create a new custom sub-agent",
)
async def create_agent(request: CreateAgentInput, svc: ServiceDep) -> Result[AgentMutationData]:
    return await upstream_agent_routes.create_agent(request, svc)


@router.post(
    "/agent/edit",
    response_model=Result[AgentMutationData],
    summary="Edit Agent",
    description="Update an existing custom sub-agent configuration",
)
async def edit_agent(request: EditAgentInput, svc: ServiceDep) -> Result[AgentMutationData]:
    return await upstream_agent_routes.edit_agent(request, svc)


@router.delete(
    "/agent/delete",
    response_model=Result[AgentMutationData],
    summary="Delete Agent",
    description="Delete a custom sub-agent from agent.yml",
)
async def delete_agent(
    svc: ServiceDep,
    agent_id: str = Query(..., description="Agent id to delete"),
) -> Result[AgentMutationData]:
    return await upstream_agent_routes.delete_agent(svc, agent_id)


@router.get(
    "/agent/tools",
    response_model=Result[AgentToolsData],
    summary="List Available Tools",
    description="Get all valid tool categories and their methods for agent configuration",
)
async def list_available_tools() -> Result[AgentToolsData]:
    return await upstream_agent_routes.list_available_tools()

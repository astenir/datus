import { ref } from "vue";
import { agentApi } from "@/lib/api";
import { useConnection } from "./useConnection";
import type { AgentInfo, AgentDetail, CreateAgentInput, EditAgentInput } from "@/types";

const agents = ref<AgentInfo[]>([]);
const agentTools = ref<Record<string, string[]>>({});

async function loadAgents() {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await agentApi.list(base);
    if (result) {
      agents.value = result.agents ?? [];
    }
  } catch {
    // silently fail — agents are optional
  }
}

async function loadTools() {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await agentApi.tools(base);
    if (result) {
      agentTools.value = result.tools ?? {};
    }
  } catch {
    /* ignore */
  }
}

async function getAgent(agentId: string): Promise<AgentDetail | null> {
  const { effectiveBase } = useConnection();
  return agentApi.get(effectiveBase(), agentId);
}

async function createAgent(input: CreateAgentInput) {
  const { effectiveBase } = useConnection();
  const result = await agentApi.create(effectiveBase(), input);
  await loadAgents();
  return result;
}

async function editAgent(input: EditAgentInput) {
  const { effectiveBase } = useConnection();
  const result = await agentApi.edit(effectiveBase(), input);
  await loadAgents();
  return result;
}

async function deleteAgent(agentId: string) {
  const { effectiveBase } = useConnection();
  await agentApi.delete(effectiveBase(), agentId);
  await loadAgents();
}

export function useAgents() {
  return {
    agents,
    agentTools,
    loadAgents,
    loadTools,
    getAgent,
    createAgent,
    editAgent,
    deleteAgent,
  };
}

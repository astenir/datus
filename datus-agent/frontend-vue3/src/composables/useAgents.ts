import { ref } from "vue";
import { agentApi } from "@/lib/api";
import { useConnection } from "./useConnection";
import type { AgentInfo, CreateAgentInput, EditAgentInput } from "@/types";

const agents = ref<AgentInfo[]>([]);

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
    loadAgents,
    createAgent,
    editAgent,
    deleteAgent,
  };
}

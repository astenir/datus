import { readonly, ref } from "vue";
import { agentApi } from "@/lib/api";
import { handleError } from "@/lib/utils";
import { useConnection } from "./useConnection";
import type { AgentInfo, CreateAgentInput, EditAgentInput } from "@/types";

const { effectiveBase } = useConnection();

const agents = ref<AgentInfo[]>([]);

async function loadAgents() {
  const base = effectiveBase();
  try {
    const result = await agentApi.list(base);
    if (result) {
      agents.value = result.agents ?? [];
    }
  } catch (error) {
    handleError("加载 Agent 列表失败", error);
  }
}

async function createAgent(input: CreateAgentInput) {
  const result = await agentApi.create(effectiveBase(), input);
  await loadAgents();
  return result;
}

async function editAgent(input: EditAgentInput) {
  const result = await agentApi.edit(effectiveBase(), input);
  await loadAgents();
  return result;
}

async function deleteAgent(agentId: string) {
  await agentApi.delete(effectiveBase(), agentId);
  await loadAgents();
}

export function useAgents() {
  return {
    agents: readonly(agents),
    loadAgents,
    createAgent,
    editAgent,
    deleteAgent,
  };
}

import { apiResult, jsonBody } from "./helpers";
import type {
  AgentDetail,
  AgentInfo,
  AgentToolsData,
  AgentUseToolsData,
  CreateAgentInput,
  EditAgentInput,
} from "@/types";

export const agentApi = {
  list(baseUrl: string): Promise<{ agents: AgentInfo[] } | null> {
    return apiResult(baseUrl, "/api/v1/agent/list");
  },

  get(baseUrl: string, agentId: string): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/agent?agent_id=${encodeURIComponent(agentId)}`);
  },

  create(baseUrl: string, input: CreateAgentInput): Promise<{ name: string } | null> {
    return apiResult(baseUrl, "/api/v1/agent/create", jsonBody(input));
  },

  edit(baseUrl: string, input: EditAgentInput): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/agent/edit", jsonBody(input));
  },

  delete(baseUrl: string, agentId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/agent/delete?agent_id=${encodeURIComponent(agentId)}`, { method: "DELETE" });
  },

  tools(baseUrl: string): Promise<AgentToolsData | null> {
    return apiResult(baseUrl, "/api/v1/agent/tools");
  },

  useTools(baseUrl: string, agentType: string): Promise<AgentUseToolsData | null> {
    return apiResult(baseUrl, `/api/v1/agent/use_tools?agent_type=${encodeURIComponent(agentType)}`);
  },
};

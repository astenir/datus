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
  list(baseUrl: string): Promise<AgentInfo[] | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents");
  },

  get(baseUrl: string, agentId: string): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}`);
  },

  create(baseUrl: string, agentId: string, input: CreateAgentInput): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}`, {
      ...jsonBody(input),
      method: "PUT",
    });
  },

  edit(baseUrl: string, agentId: string, input: EditAgentInput): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}`, {
      ...jsonBody(input),
      method: "PUT",
    });
  },

  delete(baseUrl: string, agentId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}`, { method: "DELETE" });
  },

  tools(baseUrl: string): Promise<AgentToolsData | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/tools");
  },

  useTools(baseUrl: string, nodeClass: string): Promise<AgentUseToolsData | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/tool-reference?node_class=${encodeURIComponent(nodeClass)}`);
  },
};

import { apiResult, jsonBody } from "./helpers";
import type {
  AgentAclRoleSummary,
  AgentAclUserSummary,
  AgentAcl,
  AgentDetail,
  AgentInfo,
  AgentNodeType,
  AgentPolicy,
  AgentPreferenceSummary,
  AgentToolsData,
  AgentUseToolsData,
  CreateAgentInput,
  EditAgentInput,
} from "@/types";

export const agentApi = {
  availableList(baseUrl: string): Promise<AgentInfo[] | null> {
    return apiResult(baseUrl, "/api/v1/agents");
  },

  list(baseUrl: string): Promise<AgentInfo[] | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents");
  },

  nodeTypes(baseUrl: string): Promise<AgentNodeType[] | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/node-types");
  },

  aclUsers(baseUrl: string): Promise<AgentAclUserSummary[] | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/acl-users?limit=100");
  },

  aclRoles(baseUrl: string): Promise<AgentAclRoleSummary[] | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/acl-roles?limit=100");
  },

  get(baseUrl: string, agentId: string): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}`);
  },

  policy(baseUrl: string, agentId: string): Promise<AgentPolicy | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/policy`);
  },

  updatePolicy(baseUrl: string, agentId: string, input: AgentPolicy): Promise<AgentPolicy | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/policy`, {
      ...jsonBody(input),
      method: "PUT",
    });
  },

  enterpriseDefault(baseUrl: string): Promise<AgentPreferenceSummary | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/default");
  },

  updateEnterpriseDefault(baseUrl: string, agentId: string | null): Promise<AgentPreferenceSummary | null> {
    return apiResult(baseUrl, "/api/v1/admin/agents/default", {
      ...jsonBody({ default_agent_id: agentId }),
      method: "PUT",
    });
  },

  defaultUsers(baseUrl: string, agentId: string): Promise<string[] | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/default-users`);
  },

  updateDefaultUsers(baseUrl: string, agentId: string, userIds: string[]): Promise<string[] | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/default-users`, {
      ...jsonBody({ user_ids: userIds }),
      method: "PUT",
    });
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

  updateStatus(baseUrl: string, agentId: string, status: string): Promise<AgentDetail | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/status`, {
      ...jsonBody({ status }),
      method: "PUT",
    });
  },

  updateAcl(baseUrl: string, agentId: string, input: AgentAcl): Promise<AgentAcl | null> {
    return apiResult(baseUrl, `/api/v1/admin/agents/${encodeURIComponent(agentId)}/acl`, {
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

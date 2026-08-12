import { del, get, post, put } from "@/lib/request";
import type {
  AgentPreferenceSummary,
  ApiResponse,
  MeSessionsData,
  MeSummary,
  MeUsage,
  ModelCredentialSummary,
  ModelPreferenceSummary,
  ModelProbeResult,
  ModelProviderOption,
  PersonalDatasourceProbeResult,
  PersonalDatasourceProviderOptions,
  PersonalDatasourceSummary,
  PersonalMcpConnectivityResult,
  PersonalMcpDeleteResult,
  PersonalMcpOptions,
  PersonalMcpSessionBinding,
  PersonalMcpSessionReference,
  PersonalMcpSummary,
  PersonalMcpToolSummary,
  UpdateModelPreferenceInput,
  UpdateAgentPreferenceInput,
  UpsertModelCredentialInput,
  UpsertPersonalDatasourceInput,
  UpsertPersonalMcpInput,
} from "@/types/profile";

export const meApi = {
  summary(): Promise<ApiResponse<MeSummary>> {
    return get<ApiResponse<MeSummary>>("/api/v1/me");
  },

  permissions(): Promise<ApiResponse<string[]>> {
    return get<ApiResponse<string[]>>("/api/v1/me/permissions");
  },

  datasourceGrants(): Promise<ApiResponse<Record<string, unknown>>> {
    return get<ApiResponse<Record<string, unknown>>>("/api/v1/me/datasource-grants");
  },

  features(): Promise<ApiResponse<Record<string, boolean>>> {
    return get<ApiResponse<Record<string, boolean>>>("/api/v1/me/features");
  },

  sessions(): Promise<ApiResponse<MeSessionsData>> {
    return get<ApiResponse<MeSessionsData>>("/api/v1/me/sessions");
  },

  usage(): Promise<ApiResponse<MeUsage[]>> {
    return get<ApiResponse<MeUsage[]>>("/api/v1/me/usage");
  },

  agentPreference(): Promise<ApiResponse<AgentPreferenceSummary>> {
    return get<ApiResponse<AgentPreferenceSummary>>("/api/v1/me/agent-preferences");
  },

  updateAgentPreference(input: UpdateAgentPreferenceInput): Promise<ApiResponse<AgentPreferenceSummary>> {
    return put<ApiResponse<AgentPreferenceSummary>>("/api/v1/me/agent-preferences", input);
  },

  modelProviders(): Promise<ApiResponse<ModelProviderOption[]>> {
    return get<ApiResponse<ModelProviderOption[]>>("/api/v1/me/model-providers");
  },

  modelCredentials(): Promise<ApiResponse<ModelCredentialSummary[]>> {
    return get<ApiResponse<ModelCredentialSummary[]>>("/api/v1/me/model-credentials");
  },

  createModelCredential(input: UpsertModelCredentialInput): Promise<ApiResponse<ModelCredentialSummary>> {
    return post<ApiResponse<ModelCredentialSummary>>("/api/v1/me/model-credentials", input);
  },

  updateModelCredential(
    id: string,
    input: UpsertModelCredentialInput
  ): Promise<ApiResponse<ModelCredentialSummary>> {
    return put<ApiResponse<ModelCredentialSummary>>(`/api/v1/me/model-credentials/${encodeURIComponent(id)}`, input);
  },

  deleteModelCredential(id: string): Promise<ApiResponse<{ deleted: boolean }>> {
    return del<ApiResponse<{ deleted: boolean }>>(`/api/v1/me/model-credentials/${encodeURIComponent(id)}`);
  },

  testModelCredential(id: string): Promise<ApiResponse<ModelProbeResult>> {
    return post<ApiResponse<ModelProbeResult>>(`/api/v1/me/model-credentials/${encodeURIComponent(id)}/test`);
  },

  modelPreference(): Promise<ApiResponse<ModelPreferenceSummary>> {
    return get<ApiResponse<ModelPreferenceSummary>>("/api/v1/me/model-preferences");
  },

  updateModelPreference(input: UpdateModelPreferenceInput): Promise<ApiResponse<ModelPreferenceSummary>> {
    return put<ApiResponse<ModelPreferenceSummary>>("/api/v1/me/model-preferences", input);
  },

  datasourceProviders(): Promise<ApiResponse<PersonalDatasourceProviderOptions>> {
    return get<ApiResponse<PersonalDatasourceProviderOptions>>("/api/v1/me/datasource-providers");
  },

  personalDatasources(): Promise<ApiResponse<PersonalDatasourceSummary[]>> {
    return get<ApiResponse<PersonalDatasourceSummary[]>>("/api/v1/me/datasources");
  },

  createPersonalDatasource(input: UpsertPersonalDatasourceInput): Promise<ApiResponse<PersonalDatasourceSummary>> {
    return post<ApiResponse<PersonalDatasourceSummary>>("/api/v1/me/datasources", input);
  },

  updatePersonalDatasource(
    id: string,
    input: UpsertPersonalDatasourceInput
  ): Promise<ApiResponse<PersonalDatasourceSummary>> {
    return put<ApiResponse<PersonalDatasourceSummary>>(`/api/v1/me/datasources/${encodeURIComponent(id)}`, input);
  },

  deletePersonalDatasource(id: string): Promise<ApiResponse<{ deleted: boolean }>> {
    return del<ApiResponse<{ deleted: boolean }>>(`/api/v1/me/datasources/${encodeURIComponent(id)}`);
  },

  testPersonalDatasource(id: string): Promise<ApiResponse<PersonalDatasourceProbeResult>> {
    return post<ApiResponse<PersonalDatasourceProbeResult>>(`/api/v1/me/datasources/${encodeURIComponent(id)}/test`);
  },

  personalMcpOptions(signal?: AbortSignal): Promise<ApiResponse<PersonalMcpOptions>> {
    return get<ApiResponse<PersonalMcpOptions>>("/api/v1/me/mcp-servers/options", { signal });
  },

  personalMcpServers(signal?: AbortSignal): Promise<ApiResponse<PersonalMcpSummary[]>> {
    return get<ApiResponse<PersonalMcpSummary[]>>("/api/v1/me/mcp-servers", { signal });
  },

  createPersonalMcp(
    input: UpsertPersonalMcpInput,
    signal?: AbortSignal,
  ): Promise<ApiResponse<PersonalMcpSummary>> {
    return post<ApiResponse<PersonalMcpSummary>>("/api/v1/me/mcp-servers", input, { signal });
  },

  updatePersonalMcp(
    id: string,
    input: UpsertPersonalMcpInput,
    signal?: AbortSignal,
  ): Promise<ApiResponse<PersonalMcpSummary>> {
    return put<ApiResponse<PersonalMcpSummary>>(
      `/api/v1/me/mcp-servers/${encodeURIComponent(id)}`,
      input,
      { signal },
    );
  },

  deletePersonalMcp(id: string, force = false, signal?: AbortSignal): Promise<ApiResponse<PersonalMcpDeleteResult>> {
    const query = force ? "?force=1" : "";
    return del<ApiResponse<PersonalMcpDeleteResult>>(
      `/api/v1/me/mcp-servers/${encodeURIComponent(id)}${query}`,
      { signal },
    );
  },

  personalMcpReferences(id: string, signal?: AbortSignal): Promise<ApiResponse<PersonalMcpSessionReference[]>> {
    return get<ApiResponse<PersonalMcpSessionReference[]>>(
      `/api/v1/me/mcp-servers/${encodeURIComponent(id)}/references`,
      { signal },
    );
  },

  testPersonalMcp(
    id: string,
    signal?: AbortSignal,
  ): Promise<ApiResponse<PersonalMcpConnectivityResult>> {
    return post<ApiResponse<PersonalMcpConnectivityResult>>(
      `/api/v1/me/mcp-servers/${encodeURIComponent(id)}/test`,
      undefined,
      { signal },
    );
  },

  personalMcpTools(id: string, signal?: AbortSignal): Promise<ApiResponse<PersonalMcpToolSummary[]>> {
    return get<ApiResponse<PersonalMcpToolSummary[]>>(
      `/api/v1/me/mcp-servers/${encodeURIComponent(id)}/tools`,
      { signal },
    );
  },

  personalMcpSessionBinding(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<ApiResponse<PersonalMcpSessionBinding>> {
    return get<ApiResponse<PersonalMcpSessionBinding>>(
      `/api/v1/me/mcp-servers/session-binding/${encodeURIComponent(sessionId)}`,
      { signal },
    );
  },
};

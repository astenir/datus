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
  UpdateModelPreferenceInput,
  UpdateAgentPreferenceInput,
  UpsertModelCredentialInput,
  UpsertPersonalDatasourceInput,
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
};

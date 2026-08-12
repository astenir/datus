import type { components } from "@/types/openapi";

export interface ApiResponse<T> {
  success: boolean;
  data?: T | null;
  errorCode?: string | null;
  errorMessage?: string | null;
}

export type MeSummary = components["schemas"]["MeSummary"];
export type MeSessionsData = components["schemas"]["ChatSessionData"];
export type MeSession = components["schemas"]["ChatSessionItemInfo"];

export interface MeUsage {
  subject_type: string;
  subject_id: string;
  resource: string;
  used: number;
  window_start?: string | null;
  window_seconds?: number | null;
  updated_at?: string | null;
}

export interface MeDatasourceGrantView {
  datasource: string;
  enabled: boolean;
  effect: string;
  scopeText: string;
  raw: unknown;
}

export interface MeFeatureView {
  code: string;
  label: string;
  enabled: boolean;
}

export interface ModelProviderOption {
  provider: string;
  label: string;
  default_model: string;
  models: string[];
  custom?: boolean;
  requires_base_url?: boolean;
}

export interface ModelCredentialSummary {
  id: string;
  provider: string;
  model: string;
  base_url?: string | null;
  ref_hint: string;
  display_name?: string | null;
  enabled: boolean;
  last_used_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpsertModelCredentialInput {
  provider: string;
  model: string;
  api_key: string;
  base_url?: string | null;
  display_name?: string | null;
  enabled: boolean;
}

export interface ModelPreferenceSummary {
  default_credential_id?: string | null;
  default_model?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpdateModelPreferenceInput {
  default_credential_id?: string | null;
  default_model?: string | null;
}

export type AgentPreferenceSummary = components["schemas"]["AgentPreferenceSummary"];
export type UpdateAgentPreferenceInput = components["schemas"]["UpdateAgentPreferenceRequest"];

export interface ModelProbeResult {
  ok: boolean;
  message?: string | null;
}

export interface PersonalDatasourceProviderOptions {
  enabled: boolean;
  allowed_types: string[];
  allowed_hosts: string[];
  default_ports: Record<string, string>;
}

export interface PersonalDatasourceSummary {
  id: string;
  datasource_key: string;
  type: string;
  host: string;
  port: string;
  username: string;
  password_hint: string;
  database: string;
  schema_name?: string | null;
  catalog_name?: string | null;
  display_name?: string | null;
  enabled: boolean;
  last_used_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpsertPersonalDatasourceInput {
  type: string;
  host: string;
  port: string;
  username: string;
  password: string;
  database: string;
  schema_name?: string | null;
  catalog_name?: string | null;
  display_name?: string | null;
  enabled: boolean;
}

export type PersonalDatasourceProbeResult = ModelProbeResult;

export type PersonalMcpTransport = "http" | "sse";

export interface PersonalMcpOptions {
  enabled: boolean;
  allowed_hosts: readonly string[];
  allow_insecure_http: boolean;
  allow_private_hosts: boolean;
  max_servers_per_user: number;
  max_selected_per_session: number;
}

export interface PersonalMcpSummary {
  id: string;
  display_name: string;
  transport: PersonalMcpTransport;
  url: string;
  auth_mode: "none" | "static_bearer";
  credential_configured: boolean;
  token_hint?: string | null;
  allowed_tools: readonly string[];
  blocked_tools: readonly string[];
  enabled: boolean;
  revision: number;
  last_used_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpsertPersonalMcpInput {
  display_name: string;
  transport: PersonalMcpTransport;
  url: string;
  token?: string | null;
  allowed_tools: string[];
  blocked_tools: string[];
  enabled: boolean;
}

export interface PersonalMcpConnectivityResult {
  connected: boolean;
  message: string;
  tools_count?: number | null;
}

export interface PersonalMcpToolSummary {
  name: string;
  description?: string | null;
  inputSchema?: Record<string, unknown>;
}

export interface PersonalMcpSessionBinding {
  session_id: string;
  servers: Array<{ mcp_id: string; revision: number; display_name: string }>;
}

export interface PersonalMcpSessionReference {
  session_id: string;
  title: string;
  updated_at?: string | null;
}

export interface PersonalMcpDeleteResult {
  deleted: boolean;
  unbound_sessions?: number;
}

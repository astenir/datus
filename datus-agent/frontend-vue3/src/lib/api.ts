/**
 * Unified API client for all Datus backend endpoints.
 * Uses requestJson/extractResultData from chat.ts for consistent behavior.
 */
import { requestJson, extractResultData } from "./chat";
import type {
  AgentDetail,
  AgentInfo,
  ArtifactManifest,
  BootstrapDocInput,
  BootstrapKbInput,
  ChatSessionOption,
  CompactSessionData,
  ConfigSummary,
  ContextCommandResult,
  CreateAgentInput,
  DashboardDetail,
  DatabaseInfo,
  EditAgentInput,
  InternalCommandResult,
  KnowledgeInfo,
  McpServerInfo,
  McpToolFilter,
  McpToolInfo,
  MetricInfo,
  ModelInfo,
  ModelsData,
  ProbeResult,
  ReferenceSQLInfo,
  ReportDetail,
  SemanticModelValidation,
  SqlExecuteResult,
  SubjectNode,
  SuccessStoryInput,
  SuccessStoryResult,
  TableDetail,
  UserInteractionInput,
  VisualizationResult,
} from "@/types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function api<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  return requestJson<T>(baseUrl, path, init);
}

function apiResult<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T | null> {
  return requestJson<unknown>(baseUrl, path, init).then(extractResultData<T>);
}

function jsonBody(data: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(data) };
}

function putBody(data: unknown): RequestInit {
  return { method: "PUT", body: JSON.stringify(data) };
}

// ─── Chat API ────────────────────────────────────────────────────────────────

export const chatApi = {
  sessions(baseUrl: string, subagentId?: string): Promise<{ sessions: ChatSessionOption[]; total_count: number } | null> {
    const query = subagentId ? `?subagent_id=${encodeURIComponent(subagentId)}` : "";
    return apiResult(baseUrl, `/api/v1/chat/sessions${query}`);
  },

  history(baseUrl: string, sessionId: string): Promise<{ messages: unknown[] } | null> {
    return apiResult(baseUrl, `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
  },

  stop(baseUrl: string, sessionId: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/stop", jsonBody({ session_id: sessionId }));
  },

  deleteSession(baseUrl: string, sessionId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  },

  compact(baseUrl: string, sessionId: string): Promise<CompactSessionData | null> {
    return apiResult(baseUrl, `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/compact`, { method: "POST" });
  },

  async feedback(baseUrl: string, input: { source_session_id: string; reaction_emoji: string; reference_msg: string; reaction_msg?: string }): Promise<void> {
    const response = await fetch(`${baseUrl}/api/v1/chat/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    // Feedback runs as background SSE — consume and discard
    const reader = response.body?.getReader();
    if (reader) {
      try { while (!(await reader.read()).done) { /* drain */ } } catch { /* ignore */ }
    }
  },

  userInteraction(baseUrl: string, input: UserInteractionInput): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/user_interaction", jsonBody(input));
  },

  insert(baseUrl: string, sessionId: string, message: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/insert", jsonBody({ session_id: sessionId, message }));
  },

  toolResult(baseUrl: string, callToolId: string, result: { success: 0 | 1; error?: string; result?: unknown }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/tool_result", jsonBody({ call_tool_id: callToolId, tool_result: result }));
  },
};

// ─── Agent API ───────────────────────────────────────────────────────────────

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

  tools(baseUrl: string): Promise<{ tools: Record<string, string[]> } | null> {
    return apiResult(baseUrl, "/api/v1/agent/tools");
  },

  useTools(baseUrl: string, agentType: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/agent/use_tools?agent_type=${encodeURIComponent(agentType)}`);
  },
};

// ─── Config API ──────────────────────────────────────────────────────────────

export const configApi = {
  getAgent(baseUrl: string): Promise<ConfigSummary | null> {
    return apiResult(baseUrl, "/api/v1/config/agent");
  },

  updateDatasources(baseUrl: string, datasources: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/config/datasources", putBody({ datasources }));
  },

  updateModels(baseUrl: string, models?: Record<string, unknown>, target?: string): Promise<unknown> {
    const body: Record<string, unknown> = {};
    if (models) body.models = models;
    if (target) body.target = target;
    return apiResult(baseUrl, "/api/v1/config/models", putBody(body));
  },

  testModel(baseUrl: string, probe: { type: string; model: string; api_key?: string; base_url?: string }): Promise<ProbeResult | null> {
    return apiResult(baseUrl, "/api/v1/config/models/test", jsonBody(probe));
  },

  testDatasource(baseUrl: string, probe: { type: string; [key: string]: unknown }): Promise<ProbeResult | null> {
    return apiResult(baseUrl, "/api/v1/config/datasources/test", jsonBody(probe));
  },

  /** Switch the active datasource. Requires backend endpoint POST /api/v1/config/datasources/switch. */
  switchDatasource(baseUrl: string, name: string): Promise<{ current_datasource: string } | null> {
    return apiResult(baseUrl, "/api/v1/config/datasources/switch", jsonBody({ name }));
  },
};

// ─── Models API ──────────────────────────────────────────────────────────────

export const modelsApi = {
  list(baseUrl: string): Promise<ModelsData | null> {
    return apiResult(baseUrl, "/api/v1/models");
  },
};

// ─── Catalog / Database API ──────────────────────────────────────────────────

export const catalogApi = {
  list(
    baseUrl: string,
    params?: { datasource_id?: string; catalog_name?: string; database_name?: string; schema_name?: string; include_sys_schemas?: boolean }
  ): Promise<{ databases: DatabaseInfo[] } | null> {
    const searchParams = new URLSearchParams();
    if (params?.datasource_id) searchParams.set("datasource_id", params.datasource_id);
    if (params?.catalog_name) searchParams.set("catalog_name", params.catalog_name);
    if (params?.database_name) searchParams.set("database_name", params.database_name);
    if (params?.schema_name) searchParams.set("schema_name", params.schema_name);
    if (params?.include_sys_schemas) searchParams.set("include_sys_schemas", "true");
    const query = searchParams.toString();
    return apiResult(baseUrl, `/api/v1/catalog/list${query ? `?${query}` : ""}`);
  },
};

// ─── Subject / Explorer API ──────────────────────────────────────────────────

export const subjectApi = {
  list(baseUrl: string): Promise<{ subjects: SubjectNode[] } | null> {
    return apiResult(baseUrl, "/api/v1/subject/list");
  },

  create(baseUrl: string, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/create", jsonBody({ subject_path: subjectPath }));
  },

  rename(baseUrl: string, type: string, subjectPath: string[], newSubjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/rename", jsonBody({ type, subject_path: subjectPath, new_subject_path: newSubjectPath }));
  },

  delete(baseUrl: string, type: string, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/delete", { method: "DELETE", body: JSON.stringify({ type, subject_path: subjectPath }) });
  },

  getMetric(baseUrl: string, subjectPath: string[]): Promise<MetricInfo | null> {
    return apiResult(baseUrl, "/api/v1/subject/metric", jsonBody({ subject_path: subjectPath }));
  },

  createMetric(baseUrl: string, subjectPath: string[], name: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/metric/create", jsonBody({ subject_path: subjectPath, name }));
  },

  editMetric(baseUrl: string, subjectPath: string[], yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/metric/edit", jsonBody({ subject_path: subjectPath, yaml }));
  },

  getReferenceSql(baseUrl: string, subjectPath: string[]): Promise<ReferenceSQLInfo | null> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql", jsonBody({ subject_path: subjectPath }));
  },

  createReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql/create", jsonBody(data));
  },

  editReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql/edit", jsonBody(data));
  },

  editSemanticModel(baseUrl: string, entryId: string, updateValues: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/semantic_model/edit", jsonBody({ entry_id: entryId, update_values: updateValues }));
  },

  getKnowledge(baseUrl: string, subjectPath: string[]): Promise<KnowledgeInfo | null> {
    return apiResult(baseUrl, "/api/v1/subject/knowledge", jsonBody({ subject_path: subjectPath }));
  },

  createKnowledge(baseUrl: string, subjectPath: string[], name: string, searchText: string, explanation: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/knowledge/create", jsonBody({ subject_path: subjectPath, name, search_text: searchText, explanation }));
  },

  editKnowledge(baseUrl: string, subjectPath: string[], searchText: string, explanation: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/knowledge/edit", jsonBody({ subject_path: subjectPath, search_text: searchText, explanation }));
  },
};

// ─── Table / Semantic Model API ──────────────────────────────────────────────

export const tableApi = {
  detail(baseUrl: string, table: string): Promise<{ table: TableDetail } | null> {
    return apiResult(baseUrl, `/api/v1/table/detail?table=${encodeURIComponent(table)}`);
  },

  getSemanticModel(baseUrl: string, table: string): Promise<{ yaml: string } | null> {
    return apiResult(baseUrl, `/api/v1/semantic_model?table=${encodeURIComponent(table)}`);
  },

  saveSemanticModel(baseUrl: string, table: string, yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/semantic_model", jsonBody({ table, yaml }));
  },

  validateSemanticModel(baseUrl: string, table: string, yaml: string): Promise<SemanticModelValidation | null> {
    return apiResult(baseUrl, "/api/v1/semantic_model/validate", jsonBody({ table, yaml }));
  },
};

// ─── SQL API ─────────────────────────────────────────────────────────────────

export const sqlApi = {
  execute(baseUrl: string, sqlQuery: string, options?: { database_name?: string; result_format?: string }): Promise<SqlExecuteResult | null> {
    return apiResult(baseUrl, "/api/v1/sql/execute", jsonBody({ sql_query: sqlQuery, ...options }));
  },

  stopExecute(baseUrl: string, executeTaskId: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/sql/stop_execute", jsonBody({ execute_task_id: executeTaskId }));
  },

  contextCommand(baseUrl: string, contextType: string, args?: string, databaseName?: string, schemaName?: string): Promise<ContextCommandResult | null> {
    return apiResult(baseUrl, `/api/v1/context/${encodeURIComponent(contextType)}`, jsonBody({ context_type: contextType, args: args || "", database_name: databaseName, schema_name: schemaName }));
  },

  internalCommand(baseUrl: string, command: string, args?: string): Promise<InternalCommandResult | null> {
    return apiResult(baseUrl, `/api/v1/internal/${encodeURIComponent(command)}`, jsonBody({ command, args: args || "" }));
  },
};

// ─── Knowledge Base API ──────────────────────────────────────────────────────

export const kbApi = {
  async bootstrap(baseUrl: string, input: BootstrapKbInput): Promise<ReadableStream<Uint8Array> | null> {
    const response = await fetch(`${baseUrl}/api/v1/kb/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.body;
  },

  cancelBootstrap(baseUrl: string, streamId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/kb/bootstrap/${encodeURIComponent(streamId)}/cancel`, { method: "POST" });
  },

  async bootstrapDocs(baseUrl: string, input: BootstrapDocInput): Promise<ReadableStream<Uint8Array> | null> {
    const response = await fetch(`${baseUrl}/api/v1/kb/bootstrap-docs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.body;
  },

  cancelBootstrapDocs(baseUrl: string, streamId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/kb/bootstrap-docs/${encodeURIComponent(streamId)}/cancel`, { method: "POST" });
  },
};

// ─── MCP API ─────────────────────────────────────────────────────────────────

export const mcpApi = {
  listServers(baseUrl: string, serverType?: string): Promise<{ servers: McpServerInfo[] } | null> {
    const query = serverType ? `?server_type=${encodeURIComponent(serverType)}` : "";
    return apiResult(baseUrl, `/api/v1/mcp/servers${query}`);
  },

  addServer(baseUrl: string, server: McpServerInfo): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/mcp/servers", jsonBody(server));
  },

  removeServer(baseUrl: string, serverName: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, { method: "DELETE" });
  },

  connectivity(baseUrl: string, serverName: string): Promise<{ ok: boolean; message?: string } | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/connectivity`);
  },

  listTools(baseUrl: string, serverName: string, applyFilter = true): Promise<{ tools: McpToolInfo[] } | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools?apply_filter=${applyFilter}`);
  },

  callTool(baseUrl: string, serverName: string, toolName: string, parameters?: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools/${encodeURIComponent(toolName)}/call`, jsonBody({ parameters: parameters || {} }));
  },

  getFilters(baseUrl: string, serverName: string): Promise<McpToolFilter | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`);
  },

  setFilters(baseUrl: string, serverName: string, filter: McpToolFilter): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`, putBody(filter));
  },

  removeFilters(baseUrl: string, serverName: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`, { method: "DELETE" });
  },
};

// ─── Dashboard API ───────────────────────────────────────────────────────────

export const dashboardApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/dashboard/list");
  },

  detail(baseUrl: string, slug: string): Promise<DashboardDetail | null> {
    return apiResult(baseUrl, `/api/v1/dashboard/detail?slug=${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/dashboard/html?slug=${encodeURIComponent(slug)}`;
  },

  query(baseUrl: string, dashboardSlug: string, querySlug: string, params?: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/dashboard/query", jsonBody({ dashboard_slug: dashboardSlug, query_slug: querySlug, params }));
  },
};

// ─── Report API ──────────────────────────────────────────────────────────────

export const reportApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/report/list");
  },

  detail(baseUrl: string, slug: string): Promise<ReportDetail | null> {
    return apiResult(baseUrl, `/api/v1/report/detail?slug=${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/report/html?slug=${encodeURIComponent(slug)}`;
  },
};

// ─── Visualization API ───────────────────────────────────────────────────────

export const visualizationApi = {
  recommend(
    baseUrl: string,
    csvData: { columns: string[]; data: Record<string, unknown>[] },
    options?: { chart_type?: string; sql?: string; user_question?: string }
  ): Promise<VisualizationResult | null> {
    return apiResult(baseUrl, "/api/v1/data_visualization", jsonBody({ csv_data: csvData, ...options }));
  },
};

// ─── Success Story API ───────────────────────────────────────────────────────

export const successStoryApi = {
  save(baseUrl: string, input: SuccessStoryInput): Promise<SuccessStoryResult | null> {
    return apiResult(baseUrl, "/api/v1/success-stories", jsonBody(input));
  },
};

// ─── Tool API ────────────────────────────────────────────────────────────────

export const toolApi = {
  execute(baseUrl: string, toolName: string, params?: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/tools/${encodeURIComponent(toolName)}`, jsonBody(params || {}));
  },
};

// ─── System API ──────────────────────────────────────────────────────────────

export const systemApi = {
  health(baseUrl: string): Promise<{ status?: string } | null> {
    return apiResult(baseUrl, "/health");
  },

  async authToken(baseUrl: string, clientId: string, clientSecret: string): Promise<{ access_token?: string; token_type?: string } | null> {
    const params = new URLSearchParams({ grant_type: "client_credentials", client_id: clientId, client_secret: clientSecret });
    const response = await fetch(`${baseUrl}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  },

  async workflowRun(baseUrl: string, input: Record<string, unknown>): Promise<unknown> {
    const response = await fetch(`${baseUrl}/workflows/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  },

  workflowFeedback(baseUrl: string, input: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/workflows/feedback", jsonBody(input));
  },
};

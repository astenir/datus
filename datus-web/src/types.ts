export type Role = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  blocks?: readonly MessageBlock[];
  depth?: number;
};

export type MessageOperation = "createMessage" | "appendMessage" | "updateMessage";

export type ToolCallBlock = { type: "tool-call"; callToolId?: string; toolName: string; params: unknown };
export type ToolResultBlock = {
  type: "tool-result";
  callToolId?: string;
  toolName: string;
  duration?: number;
  shortDesc?: string;
  errorText?: string;
  result?: unknown;
};
export type ToolExecutionBlock = {
  type: "tool-execution";
  callToolId: string;
  toolName: string;
  params: unknown;
  duration?: number;
  shortDesc?: string;
  errorText?: string;
  result?: unknown;
};

export type MessageBlock =
  | { type: "markdown"; content: string }
  | { type: "thinking"; content: string }
  | { type: "code"; language: string; content: string }
  | ToolCallBlock
  | ToolResultBlock
  | { type: "user-interaction"; interactionKey: string; actionType: string; requests: readonly UserInteractionRequest[] }
  | { type: "subagent-complete"; subagent: string; toolCount?: number; duration?: number; errorText?: string }
  | { type: "artifact"; kind: string; slug: string; name: string; description?: string; mode?: string };

export type MessageDisplayBlock = MessageBlock | ToolExecutionBlock;

export type ChatDisplayMessage = Omit<ChatMessage, "blocks"> & {
  blocks?: readonly MessageDisplayBlock[];
};

export type UserInteractionRequest = {
  content: string;
  options: ReadonlyArray<{ key: string; title: string }>;
  allowFreeText?: boolean;
  multiSelect?: boolean;
};

export type ParsedMessage = {
  message: ChatMessage;
  operation: MessageOperation;
};

export type AgentOption = {
  id: string;
  name: string;
  type?: string;
};

export type ChatSessionOption = {
  session_id: string;
  user_query?: unknown;
  created_at?: string;
  last_updated?: string;
  total_turns?: number;
  is_active?: boolean;
};

export type ConfigSummary = {
  target?: string;
  models?: Record<string, Record<string, unknown>>;
  current_datasource?: string;
  datasources?: Record<string, Record<string, unknown>>;
  home?: string;
};

export type SelectOption = {
  value: string;
  label: string;
};

export type ConnectionState = "idle" | "checking" | "online" | "offline";

export type SseEvent = {
  id?: string;
  event?: string;
  data?: unknown;
};

export type SseMessagePayload = {
  message_id?: string | number;
  role?: Role;
  content?: Array<{ type?: string; payload?: Record<string, unknown> }>;
  depth?: number;
};

export type CatalogRecord = Record<string, unknown>;

// ─── Navigation ──────────────────────────────────────────────────────────────

export type DeveloperViewType = "chat" | "knowledge" | "mcp" | "sql" | "dashboard" | "report";
export type ViewType = DeveloperViewType | "settings";

// ─── Agent Management ────────────────────────────────────────────────────────

export type AgentInfo = {
  name: string;
  type?: string;
  config_yaml?: string;
  system_prompt?: string;
  created_at?: string;
};

export type AgentDetail = AgentInfo & {
  tools?: string[];
  catalogs?: string[];
  subjects?: string[];
  rules?: string[];
};

export type CreateAgentInput = {
  name: string;
  datasource_id?: string;
  type?: string;
  artifact_slug?: string;
  description?: string;
  prompt_template?: string;
  prompt_version?: string;
  prompt_language?: string;
  tools?: string[];
  mcp?: string[];
  skills?: string[];
  catalogs?: string[];
  subjects?: string[];
  permissions?: Record<string, unknown>;
  hooks?: Record<string, unknown>;
  rules?: string[];
  max_turns?: number;
  workspace_root?: string;
  adapter_type?: string;
  sql_file_threshold?: number;
  sql_preview_lines?: number;
};

export type EditAgentInput = {
  id: string;
  name?: string;
  description?: string;
  prompt_template?: string;
  prompt_version?: string;
  prompt_language?: string;
  tools?: string[];
  mcp?: string[];
  skills?: string[];
  scoped_context?: Record<string, unknown>;
  permissions?: Record<string, unknown>;
  catalogs?: string[];
  subjects?: string[];
  hooks?: Record<string, unknown>;
  rules?: string[];
  max_turns?: number;
  workspace_root?: string;
  adapter_type?: string;
  sql_file_threshold?: number;
  sql_preview_lines?: number;
};

// ─── Chat Extensions ─────────────────────────────────────────────────────────

export type CompactSessionData = {
  session_id: string;
  success: boolean;
  new_token_count?: number;
  tokens_saved?: number;
  compression_ratio?: string;
  error?: string;
};

export type UserInteractionInput = {
  session_id: string;
  interaction_key: string;
  input: string[][];
};

// ─── Subject / Knowledge Explorer ────────────────────────────────────────────

export type SubjectNodeType = "directory" | "metric" | "reference_sql";

export type SubjectNode = {
  name: string;
  type?: SubjectNodeType;
  subject_path: string[];
  children?: SubjectNode[];
};

export type MetricInfo = {
  name: string;
  yaml: string;
};

export type ReferenceSQLInfo = {
  name: string;
  sql: string;
  summary: string;
  search_text: string;
};

// ─── Table / Semantic Model ──────────────────────────────────────────────────

export type ColumnInfo = {
  name: string;
  type: string;
  nullable: boolean;
  default_value?: string;
  pk: boolean;
};

export type IndexInfo = {
  name: string;
  columns: string[];
  type: string;
};

export type TableDetail = {
  name: string;
  description?: string;
  rows?: number;
  columns: ColumnInfo[];
  indexes: IndexInfo[];
};

export type SemanticModelValidation = {
  valid: boolean;
  invalid_message?: string[];
};

// ─── SQL Execution ───────────────────────────────────────────────────────────

export type SqlExecuteResult = {
  execute_task_id: string;
  sql_query: string;
  row_count?: number;
  sql_return?: string;
  result_format: string;
  execution_time: number;
  executed_at: string;
  columns?: string[];
};

export type ContextCommandResult = {
  context_type: string;
  database_name?: string;
  schema_name?: string;
  result: {
    tables?: Array<{ name: string; type?: string }>;
    total_count?: number;
    context_info?: Record<string, unknown>;
    output?: unknown;
  };
};

export type InternalCommandResult = {
  command: string;
  args: string;
  result: {
    command_output: string;
    action_taken: string;
    context_changed: boolean;
    data?: unknown;
  };
};

// ─── Configuration ───────────────────────────────────────────────────────────

export type ProbeResult = {
  ok?: boolean;
  success?: boolean;
  message?: string;
  error?: string;
  errorMessage?: string;
  [key: string]: unknown;
};

export type NormalizedProbeResult = {
  ok: boolean;
  message: string;
};

// ─── Models Catalog ──────────────────────────────────────────────────────────

export type ModelInfo = {
  provider: string;
  id: string;
  model?: string;
  name?: string;
  context_length?: number;
  max_tokens?: number;
  pricing?: { prompt?: string; completion?: string };
};

export type ModelsData = {
  models: ModelInfo[];
  providers: string[];
  current_model?: string;
  fetched_at?: string;
  source: string;
};

// ─── Database Catalog ────────────────────────────────────────────────────────

export type DatabaseInfo = {
  name: string;
  uri?: string;
  type?: string;
  current?: boolean;
  catalog_name?: string;
  schema_name?: string;
  connection_status?: string;
  tables_count?: number;
  last_accessed?: string;
  tables?: string[];
};

// ─── MCP ─────────────────────────────────────────────────────────────────────

export type McpServerInfo = {
  name: string;
  type: string;
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  timeout?: number;
  env?: Record<string, string>;
  cwd?: string;
};

export type McpToolInfo = {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
};

export type McpToolFilter = {
  enabled?: boolean;
  allowed_tools?: string[];
  blocked_tools?: string[];
};

// ─── Knowledge Base Bootstrap ────────────────────────────────────────────────

export type BootstrapComponent = "metadata" | "semantic_model" | "metrics" | "ext_knowledge" | "reference_sql";

export type BootstrapKbInput = {
  components: BootstrapComponent[];
  strategy?: "overwrite" | "check" | "incremental";
  schema_linking_type?: string;
  catalog?: string;
  database_name?: string;
  success_story?: string;
  subject_tree?: string[];
  sql_dir?: string;
  ext_knowledge?: string;
};

export type BootstrapKbEvent = {
  stream_id: string;
  component: string;
  stage: string;
  message?: string;
  error?: string;
  progress?: number;
  payload?: Record<string, unknown>;
  timestamp?: string;
};

export type BootstrapDocInput = {
  platform: string;
  build_mode?: "overwrite" | "check";
  pool_size?: number;
  source_type?: string;
  source?: string;
  version?: string;
  github_ref?: string;
  github_token?: string;
  paths?: string[];
  chunk_size?: number;
  max_depth?: number;
  include_patterns?: string[];
  exclude_patterns?: string[];
};

// ─── Dashboard / Report ──────────────────────────────────────────────────────

export type ArtifactManifest = {
  slug: string;
  name: string;
  description: string;
  kind?: string;
  created_at?: string;
  updated_at?: string;
  datasources?: string[];
  key_tables?: string[];
};

export type ArtifactFile = {
  path: string;
  content: string;
};

export type DashboardDetail = {
  slug: string;
  name: string;
  description: string;
  manifest: ArtifactManifest;
  created_at?: string;
  files: ArtifactFile[];
  templates: Array<{ path: string; content: string }>;
};

export type QueryColumnMeta = {
  name: string;
  type: string;
};

export type SqlQueryResultEnvelope = {
  executed_at: string;
  datasource: string;
  row_count: number;
  columns: QueryColumnMeta[];
  rows: Record<string, unknown>[];
  sql?: string;
};

export type ReportDetail = {
  slug: string;
  name: string;
  description: string;
  manifest: ArtifactManifest;
  created_at?: string;
  files: ArtifactFile[];
};

// ─── Data Visualization ──────────────────────────────────────────────────────

export type ChartRecommendation = {
  chart_type: "Bar" | "Line" | "Pie" | "Scatter" | "Unknown";
  columns: string[];
  numeric_columns: string[];
  x_col?: string;
  y_cols?: string[];
  reason: string;
};

export type DataInsight = {
  period?: string;
  filters?: string[];
  insight?: string;
};

export type VisualizationResult = {
  chart: ChartRecommendation;
  data_insight?: DataInsight;
};

// ─── Success Story ───────────────────────────────────────────────────────────

export type SuccessStoryInput = {
  session_id: string;
  sql: string;
  user_message: string;
  subagent_id?: string;
  session_link?: string;
};

export type SuccessStoryResult = {
  csv_path: string;
  subagent_name: string;
  session_id: string;
  session_link?: string;
  timestamp: string;
};

import type { components } from "./types/openapi";

export type Role = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  blocks?: readonly MessageBlock[];
  depth?: number;
  parentActionId?: string;
};

export type MessageOperation = "createMessage" | "appendMessage" | "updateMessage";

export type ToolChildMessage = Omit<ChatMessage, "blocks"> & {
  blocks?: readonly MessageDisplayBlock[];
};

export type ToolCallBlock = {
  type: "tool-call";
  callToolId?: string;
  toolName: string;
  params: unknown;
  childMessages?: readonly ToolChildMessage[];
};
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
  childMessages?: readonly ToolChildMessage[];
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

export type SystemStatusSummary = {
  platform_status: string;
  enterprise_enabled: boolean;
  project_id?: string | null;
  current_datasource?: string | null;
  active_tasks: number;
  known_tasks: number;
};

export type DatasourceConfigMap = Record<string, Record<string, unknown>>;

export type ModelConfigMap = Record<string, Record<string, unknown>>;

export type ModelProbeInput = {
  type: string;
  model: string;
  api_key?: string | null;
  base_url?: string | null;
  [key: string]: unknown;
};

export type DatasourceProbeInput = {
  type: string;
  [key: string]: unknown;
};

export type ConfigurationTextForms = {
  target: string;
  modelsText: string;
  datasourcesText: string;
  datasourceProbeText: string;
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
  parent_action_id?: string | null;
  parentActionId?: string | null;
};

export type CatalogRecord = Record<string, unknown>;

// ─── Navigation ──────────────────────────────────────────────────────────────

export type DeveloperViewType = "chat" | "knowledge" | "mcp" | "sql" | "dashboard" | "report";
export type ViewType = DeveloperViewType | "settings";

// ─── Agent Management ────────────────────────────────────────────────────────

export type AgentAcl = components["schemas"]["AgentAcl"];

export type AgentInfo = components["schemas"]["EnterpriseAgentSummary"];

export type AgentDetail = components["schemas"]["EnterpriseAgentDetail"];

export type CreateAgentInput = components["schemas"]["UpsertEnterpriseAgentRequest"];

export type EditAgentInput = components["schemas"]["UpsertEnterpriseAgentRequest"];

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

export type MetricDimensionItem = {
  name: string;
  type?: string | null;
  description?: string | null;
  is_primary_key?: boolean | null;
};

export type MetricDimensionsData = {
  metric: string;
  dimensions?: MetricDimensionItem[];
};

export type MetricDimensionPreflight = {
  message: string;
  invalid_dimensions?: Record<string, unknown>[];
  common_dimensions?: string[];
  suggested_metric_groups?: Record<string, unknown>[];
};

export type MetricPreviewData = {
  metric: string;
  sql?: string | null;
  database?: string | null;
  preflight_error?: MetricDimensionPreflight | null;
};

export type MetricPreviewInput = {
  subject_path: string[];
  dimensions?: string[] | null;
  time_start?: string | null;
  time_end?: string | null;
  time_granularity?: string | null;
  where?: string | null;
  limit?: number | null;
  order_by?: string[] | null;
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
  invalid_message?: string[] | null;
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

export type BootstrapComponent = "metadata" | "semantic_model" | "metrics" | "reference_sql";

export type BootstrapStrategy = "overwrite" | "check" | "incremental";

export type BootstrapBuildMode = "overwrite" | "check";

export type BootstrapKbInput = {
  components: BootstrapComponent[];
  strategy?: BootstrapStrategy;
  schema_linking_type?: string;
  catalog?: string;
  database_name?: string;
  success_story?: string | null;
  subject_tree?: string[] | null;
  sql_dir?: string | null;
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
  build_mode?: BootstrapBuildMode;
  pool_size?: number;
  source_type?: string | null;
  source?: string | null;
  version?: string | null;
  github_ref?: string | null;
  github_token?: string | null;
  paths?: string[] | null;
  chunk_size?: number | null;
  max_depth?: number | null;
  include_patterns?: string[] | null;
  exclude_patterns?: string[] | null;
};

export type KnowledgeBootstrapMode = "kb" | "docs";

export type KnowledgeBootstrapStatus = "idle" | "running" | "completed" | "cancelled" | "error";

export type KnowledgeBootstrapLogLevel = "info" | "success" | "warning" | "error";

export type KnowledgeBootstrapKbForm = {
  component: BootstrapComponent;
  strategy: BootstrapStrategy;
  schemaLinkingType: "table" | "view" | "mv" | "full";
  catalog: string;
  databaseName: string;
  successStory: string;
  subjectTreeText: string;
  sqlDir: string;
};

export type KnowledgeBootstrapDocsForm = {
  platform: string;
  buildMode: BootstrapBuildMode;
  poolSize: number;
  sourceType: string;
  source: string;
  version: string;
  githubRef: string;
  githubToken: string;
  pathsText: string;
  chunkSize: string;
  maxDepth: string;
  includePatternsText: string;
  excludePatternsText: string;
};

export type KnowledgeBootstrapForms = {
  kb: KnowledgeBootstrapKbForm;
  docs: KnowledgeBootstrapDocsForm;
};

export type KnowledgeBootstrapLogEntry = {
  id: string;
  mode: KnowledgeBootstrapMode;
  event: string;
  level: KnowledgeBootstrapLogLevel;
  message: string;
  createdAt: string;
  streamId?: string;
  component?: string;
  payload?: unknown;
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

export type ArtifactVisibility = "private" | "role" | "enterprise";

export type ArtifactShare = {
  owner_user_id: string;
  visibility: ArtifactVisibility;
  allowed_roles?: string[];
  allowed_user_ids?: string[];
};

export type ArtifactShareUpdate = {
  visibility: ArtifactVisibility;
  allowed_roles?: string[];
  allowed_user_ids?: string[];
};

export type ArtifactFile = {
  path: string;
  content: string;
};

export type QueryColumnMeta = {
  name: string;
  type: "string" | "integer" | "number" | "date" | "boolean";
};

export type DashboardTemplateParamType =
  | "string"
  | "integer"
  | "number"
  | "date"
  | "boolean"
  | "string[]"
  | "integer[]"
  | "number[]"
  | "date[]"
  | "boolean[]";

export type DashboardTemplateParam = {
  name: string;
  type: DashboardTemplateParamType;
  required?: boolean;
};

export type DashboardQueryTemplate = {
  slug: string;
  description?: string;
  datasource: string;
  params: readonly DashboardTemplateParam[];
  columns: readonly QueryColumnMeta[];
  sample_params?: Record<string, unknown>;
  sample_row_count: number;
  saved_at: string;
};

export type SqlQueryResultEnvelope = {
  executed_at: string;
  datasource: string;
  row_count: number;
  columns: readonly QueryColumnMeta[];
  rows?: readonly Record<string, unknown>[];
  sql?: string | null;
};

export type DashboardDetail = {
  slug: string;
  name: string;
  description: string;
  manifest: ArtifactManifest;
  created_at?: string;
  files: readonly ArtifactFile[];
  templates?: readonly DashboardQueryTemplate[];
};

export type ReportDetail = {
  slug: string;
  name: string;
  description: string;
  manifest: ArtifactManifest;
  created_at?: string;
  files: readonly ArtifactFile[];
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

// ─── Agent Tool Catalogs ─────────────────────────────────────────────────────

export type AgentToolCategoryData = {
  tools?: string[];
};

export type AgentUseToolsData = {
  default_tools?: string[];
  tool_types?: Record<string, AgentToolCategoryData>;
};

export type AgentToolsData = {
  tools?: Record<string, string[]>;
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

// ─── Support-Only Legacy / Compatibility APIs ───────────────────────────────

export type DirectToolResult = {
  success?: 0 | 1;
  error?: string | null;
  result?: unknown;
};

export type WorkflowRunInput = {
  workflow: string;
  datasource: string;
  task: string;
  mode?: "sync" | "async";
  task_id?: string | null;
  catalog_name?: string | null;
  database_name?: string | null;
  schema_name?: string | null;
  current_date?: string | null;
  subject_path?: string[] | null;
  ext_knowledge?: string | null;
};

export type WorkflowFeedbackInput = {
  task_id: string;
  status: "success" | "failed";
};

export type WorkflowFeedbackResult = {
  task_id: string;
  acknowledged: boolean;
  recorded_at: string;
};

import { displayValueForTool, summarizeValue, tableFromToolValue } from "@/lib/tool-display";
import { resolvePersonalMcpDisplayName } from "@/lib/personal-mcp-display";
import type { MessageDisplayBlock, ToolChildMessage } from "@/types";

export type ToolDisplayBlock = Extract<
  MessageDisplayBlock,
  { type: "tool-call" | "tool-result" | "tool-execution" }
>;

export type ToolDisplayState = "running" | "completed" | "interrupted" | "error";

export type ToolPresentationOptions = {
  isActive?: boolean;
};

export type ToolPresentation = {
  title: string;
  technicalName: string;
  state: ToolDisplayState;
  statusLabel: string;
  summary?: string;
  metadata: readonly string[];
  isSubagent: boolean;
};

type SubagentCompletion = Extract<MessageDisplayBlock, { type: "subagent-complete" }>;

const toolLabels: Readonly<Record<string, string>> = {
  ask_user: "等待用户补充",
  confirm_plan: "确认执行计划",
  todo_list: "读取执行队列",
  todo_read: "查看任务详情",
  todo_update: "更新任务状态",
  todo_write: "创建执行队列",
  task: "委派子 Agent",
  list_database: "列出数据库",
  list_databases: "列出数据库",
  list_schema: "列出 Schema",
  list_schemas: "列出 Schema",
  list_table: "列出数据表",
  list_tables: "列出数据表",
  describe_table: "查看表结构",
  search_table: "搜索数据表",
  search_tables: "搜索数据表",
  get_table_ddl: "查看建表语句",
  execute_sql: "执行 SQL",
  read_query: "查询数据",
  validate_sql: "校验 SQL",
  execute_ddl: "执行 DDL",
  validate_ddl: "校验 DDL",
  execute_write: "执行数据写入",
  transfer_query_result: "转存查询结果",
  get_migration_capabilities: "查看迁移能力",
  suggest_table_layout: "生成表布局建议",
  read_file: "读取文件",
  write_file: "写入文件",
  edit_file: "编辑文件",
  delete_file: "删除文件",
  list_directory: "列出目录",
  glob: "查找文件",
  grep: "搜索文件内容",
  bash: "执行终端命令",
  web_search: "搜索网页",
  web_fetch: "读取网页",
  search_docs: "搜索文档",
  list_document_nav: "查看文档目录",
  get_document: "读取平台文档",
  search_document: "搜索平台文档",
  search_semantic_models: "搜索语义模型",
  list_subject_tree: "查看主题目录",
  get_metrics: "获取指标定义",
  search_metrics: "搜索指标",
  get_reference_sql: "读取参考 SQL",
  search_reference_sql: "搜索参考 SQL",
  search_semantic_objects: "搜索语义对象",
  list_metrics: "列出指标",
  get_dimensions: "查看指标维度",
  query_metrics: "查询指标",
  validate_semantic: "校验语义定义",
  attribution_analyze: "执行归因分析",
  search_reference_template: "搜索参考模板",
  get_reference_template: "读取参考模板",
  render_reference_template: "渲染参考模板",
  execute_reference_template: "执行参考模板",
  parse_temporal_expressions: "解析时间表达式",
  upsert_osi_metrics: "更新 OSI 指标",
  add_memory: "添加记忆",
  edit_memory: "编辑记忆",
  search_skill_usage: "搜索 Skill 用法",
  validate_skill: "校验 Skill",
  start_new_report: "新建报表",
  bind_existing_report: "关联已有报表",
  save_query: "保存报表查询",
  start_new_dashboard: "新建仪表盘",
  bind_existing_dashboard: "关联已有仪表盘",
  save_query_template: "保存查询模板",
  validate_render: "校验产物渲染",
  create_report: "创建报表",
  update_report: "更新报表",
  create_dashboard: "创建仪表盘",
  update_dashboard: "更新仪表盘",
};

const subagentLabels: Readonly<Record<string, string>> = {
  explore: "探索数据结构",
  ask_metrics: "分析指标",
  chat_custom: "调用自定义 Agent",
  gen_dashboard: "生成仪表盘",
  gen_job: "生成数据任务",
  gen_metrics: "生成指标",
  gen_report: "生成报表",
  gen_semantic_model: "生成语义模型",
  gen_skill: "生成 Skill",
  gen_sql: "生成 SQL",
  gen_sql_summary: "生成 SQL 摘要",
  gen_table: "生成数据表",
  gen_visual_dashboard: "生成可视化仪表盘",
  gen_visual_report: "生成可视化报表",
  scheduler: "安排调度任务",
};

export function isToolDisplayBlock(block: MessageDisplayBlock): block is ToolDisplayBlock {
  return block.type === "tool-call" || block.type === "tool-result" || block.type === "tool-execution";
}

export function normalizedToolName(toolName: string) {
  return toolName.trim().toLowerCase().split(".").at(-1) ?? "";
}

export function isInteractionToolName(toolName: string) {
  const normalized = normalizedToolName(toolName);
  return normalized === "ask_user" || normalized === "confirm_plan";
}

export function isSubagentTaskName(toolName: string) {
  return normalizedToolName(toolName) === "task";
}

export function toolDisplayName(toolName: string) {
  const normalized = normalizedToolName(toolName);
  return toolLabels[normalized] ?? readableIdentifier(normalized || toolName);
}

export function subagentDisplayName(value: string) {
  const normalized = value.trim().toLowerCase();
  return subagentLabels[normalized] ?? readableIdentifier(normalized || value);
}

export function toolPresentation(
  block: ToolDisplayBlock,
  options: ToolPresentationOptions = {},
): ToolPresentation {
  const isSubagent = isSubagentTaskName(block.toolName);
  const childMessages = "childMessages" in block ? block.childMessages : undefined;
  const completion = isSubagent ? subagentCompletionFromChildren(childMessages) : null;
  const errorText = toolErrorText(block) || completion?.errorText;
  const state: ToolDisplayState = block.type === "tool-call"
    ? options.isActive === false ? "interrupted" : "running"
    : errorText || block.resultStatus === "error" ? "error" : "completed";
  const subagentType = isSubagent ? subagentTypeFromParams(toolInput(block)) : "";
  const title = subagentType ? subagentDisplayName(subagentType) : toolDisplayName(block.toolName);
  const context = isSubagent
    ? stringFromRecord(toolInput(block), ["prompt", "description"])
    : contextSummary(block.toolName, toolInput(block));
  const summary = state === "error"
    ? firstNonEmpty(errorText, toolShortDescription(block), context)
    : firstNonEmpty(toolShortDescription(block), context);
  const metadata = [
    completion?.toolCount != null ? `${completion.toolCount} 次工具调用` : childProgressLabel(childMessages),
    formatToolDuration(completion?.duration ?? toolDuration(block)),
    state === "completed" && !isSubagent ? resultSummary(toolOutput(block)) : undefined,
  ].filter((value): value is string => Boolean(value));

  return {
    title,
    technicalName: resolvePersonalMcpDisplayName(
      isSubagent && subagentType ? `${block.toolName} · ${subagentType}` : block.toolName,
    ),
    state,
    statusLabel: toolStatusLabel(state),
    ...(summary ? { summary: truncate(summary, 140) } : {}),
    metadata,
    isSubagent,
  };
}

function toolStatusLabel(state: ToolDisplayState) {
  if (state === "running") return "执行中";
  if (state === "interrupted") return "已中断";
  if (state === "error") return "执行失败";
  return "已完成";
}

export function visibleToolChildMessages(messages: readonly ToolChildMessage[] | undefined) {
  return (messages ?? []).filter((message) =>
    !message.blocks?.length || message.blocks.some((block) => block.type !== "subagent-complete"),
  );
}

function toolInput(block: ToolDisplayBlock): unknown {
  return block.type === "tool-result" ? undefined : block.params;
}

function toolOutput(block: ToolDisplayBlock): unknown {
  return block.type === "tool-call" ? undefined : block.result;
}

function toolErrorText(block: ToolDisplayBlock) {
  return block.type === "tool-call" ? undefined : block.errorText;
}

function toolShortDescription(block: ToolDisplayBlock) {
  return block.shortDesc;
}

function toolDuration(block: ToolDisplayBlock) {
  return block.type === "tool-call" ? undefined : block.duration;
}

function subagentCompletionFromChildren(
  messages: readonly ToolChildMessage[] | undefined,
): SubagentCompletion | null {
  for (const message of [...(messages ?? [])].reverse()) {
    for (const block of [...(message.blocks ?? [])].reverse()) {
      if (block.type === "subagent-complete") return block;
    }
  }
  return null;
}

function subagentTypeFromParams(value: unknown) {
  return stringFromRecord(value, ["type", "subagent_type", "subagentType"]);
}

function contextSummary(toolName: string, value: unknown) {
  const normalized = normalizedToolName(toolName);
  if (normalized === "list_database" || normalized === "list_databases") {
    return labeledScopeSummary(value, [
      { keys: ["datasource", "datasource_id", "datasourceId"], label: "数据源" },
      { keys: ["catalog"], label: "Catalog" },
    ]);
  }
  if (normalized === "list_schema" || normalized === "list_schemas") {
    return namespaceSummary(value, { includeSchema: false });
  }
  if (normalized === "list_table" || normalized === "list_tables") {
    return namespaceSummary(value, { includeSchema: true });
  }
  if (normalized === "search_table" || normalized === "search_tables") {
    return searchContextSummary(value);
  }
  if (normalized === "list_subject_tree") {
    return stringFromRecord(value, ["subject_path", "subjectPath", "path"]);
  }
  if (normalized === "glob" || normalized === "grep") {
    return stringFromRecord(value, ["pattern"]);
  }

  return stringFromRecord(value, [
    "prompt",
    "description",
    "table",
    "table_name",
    "path",
    "query",
    "sql",
    "statement",
  ]);
}

function namespaceSummary(value: unknown, options: { includeSchema: boolean }) {
  if (!isRecord(value)) return undefined;
  const catalog = stringFromRecord(value, ["catalog"]);
  const database = stringFromRecord(value, ["database", "database_name", "databaseName"]);
  const schema = options.includeSchema
    ? stringFromRecord(value, ["schema_name", "schemaName", "schema"])
    : undefined;
  const namespace = [catalog, database, schema].filter((entry): entry is string => Boolean(entry));
  if (namespace.length > 1) return namespace.join(".");
  if (schema) return `Schema ${schema}`;
  if (database) return `数据库 ${database}`;
  if (catalog) return `Catalog ${catalog}`;
  return labeledScopeSummary(value, [
    { keys: ["datasource", "datasource_id", "datasourceId"], label: "数据源" },
  ]);
}

function searchContextSummary(value: unknown) {
  const direct = stringFromRecord(value, [
    "query_text",
    "queryText",
    "query",
    "keyword",
    "search_text",
    "searchText",
    "description",
  ]);
  if (direct || !isRecord(value)) return direct;
  const keywords = value.keywords;
  if (!Array.isArray(keywords)) return undefined;
  const normalized = keywords
    .filter((keyword): keyword is string => typeof keyword === "string")
    .map((keyword) => keyword.trim())
    .filter(Boolean);
  return normalized.length ? normalized.join("、") : undefined;
}

function labeledScopeSummary(
  value: unknown,
  scopes: ReadonlyArray<{ keys: readonly string[]; label: string }>,
) {
  for (const scope of scopes) {
    const candidate = stringFromRecord(value, scope.keys);
    if (candidate) return `${scope.label} ${candidate}`;
  }
  return undefined;
}

function childProgressLabel(messages: readonly ToolChildMessage[] | undefined) {
  const count = visibleToolChildMessages(messages).length;
  return count > 0 ? `${count} 条执行进展` : undefined;
}

function resultSummary(value: unknown) {
  const displayValue = displayValueForTool("result", value);
  const table = tableFromToolValue(displayValue);
  if (table?.sourceLabel) return table.sourceLabel;

  const summary = summarizeValue(displayValue);
  return summary === "空" || summary === "文本" ? undefined : summary;
}

function stringFromRecord(value: unknown, keys: readonly string[]) {
  if (!isRecord(value)) return undefined;
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate !== "string") continue;
    const normalized = candidate.trim();
    if (normalized) return normalized;
  }
  return undefined;
}

export function formatToolDuration(value: number | undefined) {
  if (value == null || !Number.isFinite(value) || value < 0) return undefined;
  if (value < 10) return `${value.toFixed(2)} 秒`;
  if (value < 60) return `${value.toFixed(1)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
}

function readableIdentifier(value: string) {
  return value
    .split(/[._-]+/)
    .filter(Boolean)
    .join(" ") || "工具调用";
}

function firstNonEmpty(...values: Array<string | undefined>) {
  return values.find((value) => value?.trim())?.trim();
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1).trimEnd()}…` : value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

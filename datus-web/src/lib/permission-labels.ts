export interface PermissionBadgeItem {
  code: string;
  kind: "regular" | "wildcard";
  label: string;
}

export type PermissionRisk = "low" | "medium" | "high";

export interface PermissionOption {
  value: string;
  kind: PermissionBadgeItem["kind"];
  label: string;
  description: string;
  risk: PermissionRisk;
  requires: string[];
}

export interface PermissionOptionGroup {
  id: string;
  label: string;
  options: PermissionOption[];
}

export type PermissionPresetGroupId = "basic" | "analysis" | "governance" | "ops";

export interface PermissionPreset {
  id: string;
  group: PermissionPresetGroupId;
  label: string;
  description: string;
  permissions: string[];
  risk: PermissionRisk;
}

export interface PermissionPresetGroup {
  id: PermissionPresetGroupId;
  label: string;
  presets: PermissionPreset[];
}

type PermissionDefinition = {
  code: string;
  label: string;
  description: string;
  risk: PermissionRisk;
  requires?: string[];
};

const permissionDefinitions: PermissionDefinition[] = [
  { code: "chat", label: "对话", description: "旧版功能别名。", risk: "low" },
  { code: "sql_generation", label: "SQL 生成", description: "旧版功能别名。", risk: "medium" },
  { code: "report", label: "报表", description: "旧版功能别名。", risk: "low" },
  { code: "dashboard", label: "仪表盘", description: "旧版功能别名。", risk: "low" },
  { code: "admin", label: "管理", description: "旧版管理别名。", risk: "high" },
  { code: "catalog", label: "数据目录", description: "旧版数据目录别名。", risk: "low" },
  { code: "*", label: "全部权限", description: "匹配所有后端权限。", risk: "high" },
  { code: "module.*", label: "全部功能权限", description: "匹配所有 module.* 权限。", risk: "high" },
  { code: "module.admin.*", label: "全部管理权限", description: "匹配所有 module.admin.* 权限。", risk: "high" },
  { code: "module.report.*", label: "全部报表权限", description: "匹配所有 module.report.* 权限。", risk: "medium" },
  { code: "module.dashboard.*", label: "全部仪表盘权限", description: "匹配所有 module.dashboard.* 权限。", risk: "medium" },
  { code: "module.config.*", label: "全部配置权限", description: "匹配所有 module.config.* 权限。", risk: "high" },
  { code: "mcp.*", label: "全部 MCP 权限", description: "匹配所有 mcp.* 操作权限。", risk: "high", requires: ["module.mcp"] },
  { code: "module.chat", label: "对话", description: "进入对话和会话能力。", risk: "low" },
  { code: "module.sql_executor", label: "SQL 执行", description: "允许使用 SQL 执行能力。", risk: "medium" },
  { code: "module.datasource_catalog", label: "数据目录", description: "允许读取授权范围内的数据目录。", risk: "low" },
  { code: "module.report.view", label: "报表查看", description: "查看可访问报表。", risk: "low" },
  { code: "module.report.query", label: "报表查询", description: "通过报表能力发起查询。", risk: "medium", requires: ["module.report.view"] },
  { code: "module.report.export", label: "报表导出", description: "导出报表结果。", risk: "high", requires: ["module.report.view"] },
  { code: "module.dashboard.view", label: "仪表盘查看", description: "查看可访问仪表盘。", risk: "low" },
  { code: "module.dashboard.query", label: "仪表盘查询", description: "通过仪表盘能力发起查询。", risk: "medium", requires: ["module.dashboard.view"] },
  { code: "module.dashboard.export", label: "仪表盘导出", description: "导出仪表盘结果。", risk: "high", requires: ["module.dashboard.view"] },
  { code: "module.kb", label: "知识库", description: "使用知识库和 RAG 能力。", risk: "medium" },
  { code: "module.mcp", label: "MCP", description: "进入 MCP 能力域。", risk: "medium" },
  { code: "mcp.server.list", label: "MCP Server 查看", description: "查看 MCP Server 列表。", risk: "low", requires: ["module.mcp"] },
  { code: "mcp.server.tools", label: "MCP Server 工具查看", description: "查看 MCP Server 暴露的工具。", risk: "low", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.server.connectivity", label: "MCP Server 连接检查", description: "检查 MCP Server 连接状态。", risk: "medium", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.server.add", label: "MCP Server 新增", description: "新增 MCP Server 配置。", risk: "high", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.server.edit", label: "MCP Server 编辑", description: "编辑 MCP Server 配置。", risk: "high", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.server.remove", label: "MCP Server 删除", description: "删除 MCP Server 配置。", risk: "high", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.filter.view", label: "MCP 过滤查看", description: "查看 MCP 工具过滤规则。", risk: "low", requires: ["module.mcp", "mcp.server.list"] },
  { code: "mcp.filter.set", label: "MCP 过滤设置", description: "设置 MCP 工具过滤规则。", risk: "high", requires: ["module.mcp", "mcp.server.list", "mcp.filter.view"] },
  { code: "mcp.filter.remove", label: "MCP 过滤删除", description: "删除 MCP 工具过滤规则。", risk: "high", requires: ["module.mcp", "mcp.server.list", "mcp.filter.view"] },
  { code: "module.config.view", label: "配置查看", description: "查看运行配置。", risk: "low" },
  { code: "module.config.edit", label: "配置编辑", description: "修改运行配置。", risk: "high", requires: ["module.config.view"] },
  { code: "module.admin.users", label: "用户管理", description: "管理企业用户。", risk: "high" },
  { code: "module.admin.roles", label: "角色管理", description: "管理角色和权限。", risk: "high" },
  { code: "module.admin.datasources", label: "数据授权管理", description: "管理数据源授权。", risk: "high" },
  { code: "module.admin.sessions", label: "会话管理", description: "查看和处置会话。", risk: "high" },
  { code: "module.admin.artifacts", label: "产物 ACL 管理", description: "管理报表和仪表盘 ACL。", risk: "high" },
  { code: "module.admin.audit", label: "审计查看", description: "查看审计日志。", risk: "medium" },
  { code: "module.admin.audit.export", label: "审计导出", description: "导出审计日志。", risk: "high", requires: ["module.admin.audit"] },
  { code: "module.admin.quotas", label: "额度管理", description: "管理用户或角色额度。", risk: "high" },
  { code: "module.admin.secrets", label: "密钥管理", description: "管理密钥引用元数据。", risk: "high" },
  { code: "module.admin.agents", label: "Agent 管理", description: "管理企业 Agent。", risk: "high" },
  { code: "module.system.status", label: "系统状态", description: "查看系统状态。", risk: "low" },
];

const definitionByCode = new Map(permissionDefinitions.map((item) => [item.code, item]));
const labelByCode = new Map(permissionDefinitions.map((item) => [item.code, item.label]));

const wildcardLabels: Record<string, string> = {
  "*": "全部权限",
  "module.*": "全部功能权限",
  "module.admin.*": "全部管理权限",
  "module.report.*": "全部报表权限",
  "module.dashboard.*": "全部仪表盘权限",
  "module.config.*": "全部配置权限",
  "mcp.*": "全部 MCP 权限",
};

const enterpriseRolePermissionCodes = [
  "*",
  "module.*",
  "module.admin.*",
  "module.report.*",
  "module.dashboard.*",
  "module.config.*",
  "mcp.*",
  "module.chat",
  "module.sql_executor",
  "module.datasource_catalog",
  "module.report.view",
  "module.report.query",
  "module.report.export",
  "module.dashboard.view",
  "module.dashboard.query",
  "module.dashboard.export",
  "module.kb",
  "module.mcp",
  "mcp.server.list",
  "mcp.server.tools",
  "mcp.server.connectivity",
  "mcp.server.add",
  "mcp.server.edit",
  "mcp.server.remove",
  "mcp.filter.view",
  "mcp.filter.set",
  "mcp.filter.remove",
  "module.config.view",
  "module.config.edit",
  "module.admin.users",
  "module.admin.roles",
  "module.admin.datasources",
  "module.admin.sessions",
  "module.admin.artifacts",
  "module.admin.audit",
  "module.admin.audit.export",
  "module.admin.quotas",
  "module.admin.secrets",
  "module.admin.agents",
  "module.system.status",
] as const;

const enterpriseRolePermissionGroupCodes = [
  {
    id: "wildcard",
    label: "特殊权限",
    codes: [
      "*",
      "module.*",
      "module.admin.*",
      "module.report.*",
      "module.dashboard.*",
      "module.config.*",
      "mcp.*",
    ],
  },
  {
    id: "core",
    label: "核心功能",
    codes: [
      "module.chat",
      "module.sql_executor",
      "module.datasource_catalog",
      "module.kb",
      "module.mcp",
      "module.system.status",
    ],
  },
  {
    id: "mcp",
    label: "MCP 管理",
    codes: [
      "mcp.server.list",
      "mcp.server.tools",
      "mcp.server.connectivity",
      "mcp.server.add",
      "mcp.server.edit",
      "mcp.server.remove",
      "mcp.filter.view",
      "mcp.filter.set",
      "mcp.filter.remove",
    ],
  },
  {
    id: "artifacts",
    label: "报表与仪表盘",
    codes: [
      "module.report.view",
      "module.report.query",
      "module.report.export",
      "module.dashboard.view",
      "module.dashboard.query",
      "module.dashboard.export",
    ],
  },
  {
    id: "config",
    label: "配置",
    codes: ["module.config.view", "module.config.edit"],
  },
  {
    id: "admin",
    label: "管理后台",
    codes: [
      "module.admin.users",
      "module.admin.roles",
      "module.admin.datasources",
      "module.admin.sessions",
      "module.admin.artifacts",
      "module.admin.audit",
      "module.admin.audit.export",
      "module.admin.quotas",
      "module.admin.secrets",
      "module.admin.agents",
    ],
  },
] as const;

const permissionPresetGroups: Array<Pick<PermissionPresetGroup, "id" | "label">> = [
  { id: "basic", label: "基础使用" },
  { id: "analysis", label: "数据分析" },
  { id: "governance", label: "治理管理" },
  { id: "ops", label: "平台运维" },
];

export const ROLE_PERMISSION_PRESETS: PermissionPreset[] = [
  {
    id: "workspace-basic",
    group: "basic",
    label: "工作台基础",
    description: "对话、数据上下文选择、配置查看和系统状态，适合大多数普通用户。",
    permissions: ["module.chat", "module.datasource_catalog", "module.config.view", "module.system.status"],
    risk: "low",
  },
  {
    id: "sql-analysis",
    group: "analysis",
    label: "SQL 分析",
    description: "使用 SQL 执行能力，仍受数据源授权和 SQL 策略约束。",
    permissions: ["module.sql_executor"],
    risk: "medium",
  },
  {
    id: "artifact-viewer",
    group: "analysis",
    label: "报表仪表盘查看",
    description: "查看被授权的报表和仪表盘。",
    permissions: ["module.report.view", "module.dashboard.view"],
    risk: "low",
  },
  {
    id: "artifact-operator",
    group: "analysis",
    label: "报表仪表盘运营",
    description: "查询和导出报表、仪表盘结果。",
    permissions: [
      "module.report.view",
      "module.report.query",
      "module.report.export",
      "module.dashboard.view",
      "module.dashboard.query",
      "module.dashboard.export",
    ],
    risk: "high",
  },
  {
    id: "knowledge-user",
    group: "basic",
    label: "知识库使用",
    description: "使用知识库和 RAG 能力。",
    permissions: ["module.kb"],
    risk: "medium",
  },
  {
    id: "mcp-observer",
    group: "basic",
    label: "MCP 查看",
    description: "打开 MCP 页面，查看 Server、工具和连接状态。",
    permissions: [
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
      "mcp.server.connectivity",
    ],
    risk: "medium",
  },
  {
    id: "user-role-admin",
    group: "governance",
    label: "用户角色管理",
    description: "管理企业用户、角色和角色权限。",
    permissions: ["module.admin.users", "module.admin.roles"],
    risk: "high",
  },
  {
    id: "governance-admin",
    group: "governance",
    label: "数据产物治理",
    description: "管理数据源授权和报表、仪表盘 ACL。",
    permissions: ["module.admin.datasources", "module.admin.artifacts"],
    risk: "high",
  },
  {
    id: "audit-viewer",
    group: "governance",
    label: "审计查看",
    description: "查看审计日志和系统状态。",
    permissions: ["module.admin.audit", "module.system.status"],
    risk: "medium",
  },
  {
    id: "platform-ops",
    group: "ops",
    label: "平台运维",
    description: "维护配置、会话、额度、密钥引用和企业 Agent。",
    permissions: [
      "module.config.view",
      "module.config.edit",
      "module.admin.sessions",
      "module.admin.quotas",
      "module.admin.secrets",
      "module.admin.agents",
      "module.system.status",
    ],
    risk: "high",
  },
  {
    id: "enterprise-admin",
    group: "ops",
    label: "企业管理员",
    description: "授予全部功能和管理权限。",
    permissions: ["*"],
    risk: "high",
  },
];

export const ROLE_PERMISSION_PRESET_GROUPS: PermissionPresetGroup[] = permissionPresetGroups.map((group) => ({
  ...group,
  presets: ROLE_PERMISSION_PRESETS.filter((preset) => preset.group === group.id),
}));

function fallbackLabel(code: string): string {
  if (code.startsWith("module.")) return code.slice("module.".length).replaceAll(".", " / ");
  return code;
}

function permissionLabel(code: string): string {
  return wildcardLabels[code] ?? labelByCode.get(code) ?? fallbackLabel(code);
}

function rolePermissionOption(code: string): PermissionOption {
  const definition = definitionByCode.get(code);
  return {
    value: code,
    kind: code.includes("*") ? "wildcard" : "regular",
    label: permissionLabel(code),
    description: definition?.description ?? "自定义权限。",
    risk: definition?.risk ?? (code.includes("*") ? "high" : "medium"),
    requires: definition?.requires ?? [],
  };
}

export const ROLE_PERMISSION_OPTIONS: PermissionOption[] = enterpriseRolePermissionCodes.map((code) =>
  rolePermissionOption(code)
);

const optionByValue = new Map(ROLE_PERMISSION_OPTIONS.map((option) => [option.value, option]));

export const ROLE_PERMISSION_GROUPS: PermissionOptionGroup[] = enterpriseRolePermissionGroupCodes.map((group) => ({
  id: group.id,
  label: group.label,
  options: group.codes.map((code) => optionByValue.get(code) ?? rolePermissionOption(code)),
}));

const permissionOrder: Map<string, number> = new Map(enterpriseRolePermissionCodes.map((code, index) => [code, index]));

export function permissionBadgeItems(permissions: readonly string[] = []): PermissionBadgeItem[] {
  const selected = new Map<string, PermissionBadgeItem>();

  for (const permission of permissions) {
    const code = permission.trim();
    if (!code) continue;

    if (code.includes("*")) {
      selected.set(code, {
        code,
        kind: "wildcard",
        label: permissionLabel(code),
      });
      continue;
    }

    selected.set(code, {
      code,
      kind: "regular",
      label: permissionLabel(code),
    });
  }

  return [...selected.values()];
}

export function permissionRiskLabel(risk: PermissionRisk): string {
  if (risk === "high") return "高风险";
  if (risk === "medium") return "中风险";
  return "低风险";
}

export function permissionMatches(required: string, granted: string): boolean {
  const requiredCode = required.trim();
  const grantedCode = granted.trim();
  if (!requiredCode || !grantedCode) return false;
  if (grantedCode === "*" || grantedCode === requiredCode) return true;

  const pattern = grantedCode
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*");
  return new RegExp(`^${pattern}$`).test(requiredCode);
}

export function permissionSelectionCovers(permissions: readonly string[], required: string): boolean {
  return permissions.some((permission) => permissionMatches(required, permission));
}

export function normalizePermissionSelection(permissions: readonly string[]): string[] {
  const selected = new Set(uniquePermissionCodes(permissions));
  let changed = true;

  while (changed) {
    changed = false;
    for (const permission of [...selected]) {
      const option = optionByValue.get(permission) ?? rolePermissionOption(permission);
      for (const required of option.requires) {
        if (!permissionSelectionCovers([...selected], required)) {
          selected.add(required);
          changed = true;
        }
      }
    }
  }

  return orderPermissionCodes([...selected]);
}

export function togglePermissionSelection(permissions: readonly string[], permission: string): string[] {
  const code = permission.trim();
  if (!code) return normalizePermissionSelection(permissions);

  const selected = new Set(uniquePermissionCodes(permissions));
  if (!selected.has(code)) {
    selected.add(code);
    return normalizePermissionSelection([...selected]);
  }

  selected.delete(code);
  let changed = true;
  while (changed) {
    changed = false;
    for (const selectedCode of [...selected]) {
      const option = optionByValue.get(selectedCode) ?? rolePermissionOption(selectedCode);
      const missingRequired = option.requires.some((required) => !permissionSelectionCovers([...selected], required));
      if (missingRequired) {
        selected.delete(selectedCode);
        changed = true;
      }
    }
  }

  return orderPermissionCodes([...selected]);
}

export function applyPermissionPresetSelection(
  permissions: readonly string[],
  presetId: string,
): string[] {
  const preset = ROLE_PERMISSION_PRESETS.find((item) => item.id === presetId);
  if (!preset) return normalizePermissionSelection(permissions);
  return normalizePermissionSelection([...permissions, ...preset.permissions]);
}

export function togglePermissionPresetSelection(
  permissions: readonly string[],
  presetId: string,
): string[] {
  const preset = ROLE_PERMISSION_PRESETS.find((item) => item.id === presetId);
  if (!preset) return normalizePermissionSelection(permissions);

  if (!permissionPresetSelected(permissions, preset)) {
    return applyPermissionPresetSelection(permissions, presetId);
  }

  const normalized = normalizePermissionSelection(permissions);
  const presetPermissions = new Set(preset.permissions);
  const sharedPresetPermissions = new Set(
    ROLE_PERMISSION_PRESETS
      .filter((item) =>
        item.id !== presetId
        && !item.permissions.every((permission) => presetPermissions.has(permission))
        && permissionPresetSelected(normalized, item)
      )
      .flatMap((item) => item.permissions),
  );
  return pruneInvalidPermissionSelection(
    uniquePermissionCodes(normalized).filter(
      (permission) => !presetPermissions.has(permission) || sharedPresetPermissions.has(permission),
    ),
  );
}

export function permissionPresetSelected(permissions: readonly string[], preset: PermissionPreset): boolean {
  const normalized = normalizePermissionSelection(permissions);
  return preset.permissions.every((permission) => normalized.includes(permission));
}

function pruneInvalidPermissionSelection(permissions: readonly string[]): string[] {
  const selected = new Set(uniquePermissionCodes(permissions));
  let changed = true;

  while (changed) {
    changed = false;
    for (const selectedCode of [...selected]) {
      const option = optionByValue.get(selectedCode) ?? rolePermissionOption(selectedCode);
      const missingRequired = option.requires.some((required) => !permissionSelectionCovers([...selected], required));
      if (missingRequired) {
        selected.delete(selectedCode);
        changed = true;
      }
    }
  }

  return orderPermissionCodes([...selected]);
}

function uniquePermissionCodes(permissions: readonly string[]): string[] {
  return [...new Set(permissions.map((permission) => permission.trim()).filter(Boolean))];
}

function orderPermissionCodes(permissions: readonly string[]): string[] {
  return [...permissions].sort((left, right) => {
    const leftOrder = permissionOrder.get(left);
    const rightOrder = permissionOrder.get(right);
    if (leftOrder !== undefined && rightOrder !== undefined) return leftOrder - rightOrder;
    if (leftOrder !== undefined) return -1;
    if (rightOrder !== undefined) return 1;
    return left.localeCompare(right);
  });
}

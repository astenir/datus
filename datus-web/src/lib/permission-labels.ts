export interface PermissionBadgeItem {
  code: string;
  kind: "regular" | "wildcard";
  label: string;
}

export interface PermissionOption {
  value: string;
  kind: PermissionBadgeItem["kind"];
  label: string;
}

export interface PermissionOptionGroup {
  id: string;
  label: string;
  options: PermissionOption[];
}

const modulePermissionLabels: Array<Omit<PermissionBadgeItem, "kind">> = [
  { code: "chat", label: "对话" },
  { code: "sql_generation", label: "SQL 生成" },
  { code: "report", label: "报表" },
  { code: "dashboard", label: "仪表盘" },
  { code: "admin", label: "管理" },
  { code: "catalog", label: "数据目录" },
  { code: "module.chat", label: "对话" },
  { code: "module.sql_executor", label: "SQL 执行" },
  { code: "module.datasource_catalog", label: "数据目录" },
  { code: "module.report.view", label: "报表查看" },
  { code: "module.report.query", label: "报表查询" },
  { code: "module.dashboard.view", label: "仪表盘查看" },
  { code: "module.dashboard.query", label: "仪表盘查询" },
  { code: "module.kb", label: "知识库" },
  { code: "module.mcp", label: "MCP" },
  { code: "module.config.view", label: "配置查看" },
  { code: "module.config.edit", label: "配置编辑" },
  { code: "module.admin.users", label: "用户管理" },
  { code: "module.admin.roles", label: "角色管理" },
  { code: "module.admin.datasources", label: "数据授权管理" },
  { code: "module.admin.sessions", label: "会话管理" },
  { code: "module.admin.artifacts", label: "产物 ACL 管理" },
  { code: "module.admin.audit", label: "审计查看" },
  { code: "module.admin.audit.export", label: "审计导出" },
  { code: "module.admin.quotas", label: "额度管理" },
  { code: "module.admin.secrets", label: "密钥管理" },
  { code: "module.admin.agents", label: "Agent 管理" },
  { code: "module.system.status", label: "系统状态" },
];

const labelByCode = new Map(modulePermissionLabels.map((item) => [item.code, item.label]));

const wildcardLabels: Record<string, string> = {
  "*": "全部权限",
  "module.*": "全部功能权限",
  "module.admin.*": "全部管理权限",
  "module.report.*": "全部报表权限",
  "module.dashboard.*": "全部仪表盘权限",
  "module.config.*": "全部配置权限",
};

const enterpriseRolePermissionCodes = [
  "module.*",
  "module.admin.*",
  "module.report.*",
  "module.dashboard.*",
  "module.config.*",
  "module.chat",
  "module.sql_executor",
  "module.datasource_catalog",
  "module.report.view",
  "module.report.query",
  "module.dashboard.view",
  "module.dashboard.query",
  "module.kb",
  "module.mcp",
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
      "module.*",
      "module.admin.*",
      "module.report.*",
      "module.dashboard.*",
      "module.config.*",
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
    id: "artifacts",
    label: "报表与仪表盘",
    codes: ["module.report.view", "module.report.query", "module.dashboard.view", "module.dashboard.query"],
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

function fallbackLabel(code: string): string {
  if (code.startsWith("module.")) return code.slice("module.".length).replaceAll(".", " / ");
  return code;
}

function permissionLabel(code: string): string {
  return wildcardLabels[code] ?? labelByCode.get(code) ?? fallbackLabel(code);
}

function rolePermissionOption(code: string): PermissionOption {
  return {
    value: code,
    kind: code.includes("*") ? "wildcard" : "regular",
    label: permissionLabel(code),
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

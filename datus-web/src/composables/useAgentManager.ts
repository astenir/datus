import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { usePermission } from "@/composables/usePermission";
import { adminArtifactApi, adminDatasourceApi, agentApi, mcpApi } from "@/lib/api";
import { ApiResultError } from "@/lib/chat";
import { adminDatasourceLabel } from "@/lib/datasource-display";
import type {
  AgentAclRoleSummary,
  AgentAclUserSummary,
  AgentDetail,
  AgentInfo,
  AgentNodeType,
  AgentPolicy,
  AgentToolsData,
  AgentUseToolsData,
  AgentVisibility,
  CreateAgentInput,
  EditAgentInput,
  McpServerInfo,
} from "@/types";
import type { AdminArtifact, AdminDatasource } from "@/types/admin";

export interface AgentFormState {
  id: string;
  name: string;
  nodeClass: string;
  status: string;
  datasourceId: string;
  artifactSlug: string;
  description: string;
  promptTemplate: string;
  toolsText: string;
  mcpText: string;
  skillsText: string;
  catalogsText: string;
  subjectsText: string;
  rulesText: string;
  maxTurns: string;
  visibility: AgentVisibility;
  allowedRoleIds: string[];
  allowedUserIds: string[];
  toolPolicyMode: "inherit" | "allowlist";
  deniedToolsText: string;
  maxPermissionMode: "normal" | "auto" | "dangerous";
  allowSubagentDelegation: boolean;
  allowedSubagentIds: string[];
  defaultUserIds: string[];
}

export type AgentFormMode = "create" | "edit";

export interface AgentMcpServerOption {
  name: string;
  type: string;
  target: string;
  tools: string[];
  selected: boolean;
  missing: boolean;
}

export interface AgentSelectOption {
  value: string;
  label: string;
  description?: string;
}

type AgentListFormField =
  | "toolsText"
  | "deniedToolsText"
  | "mcpText"
  | "skillsText"
  | "catalogsText"
  | "subjectsText"
  | "rulesText";

function emptyForm(): AgentFormState {
  return {
    id: "",
    name: "",
    nodeClass: "gen_sql",
    status: "draft",
    datasourceId: "",
    artifactSlug: "",
    description: "",
    promptTemplate: "",
    toolsText: "",
    mcpText: "",
    skillsText: "",
    catalogsText: "",
    subjectsText: "",
    rulesText: "",
    maxTurns: "",
    visibility: "enterprise",
    allowedRoleIds: [],
    allowedUserIds: [],
    toolPolicyMode: "allowlist",
    deniedToolsText: "filesystem_tools.write_file\nfilesystem_tools.edit_file\nfilesystem_tools.delete_file\nbash_tools.*",
    maxPermissionMode: "normal",
    allowSubagentDelegation: false,
    allowedSubagentIds: [],
    defaultUserIds: [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseListText(value: string | undefined): string[] | undefined {
  const items = (value ?? "")
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean);

  return items.length > 0 ? items : undefined;
}

function listText(value: string[] | undefined): string {
  return value?.join("\n") ?? "";
}

function uniqueStrings(values: readonly string[]): string[] {
  return [...new Set(values.map(value => value.trim()).filter(Boolean))];
}

function toggleSelectedValue(values: readonly string[], value: string): string[] {
  const normalized = value.trim();
  if (!normalized) return [...values];
  return values.includes(normalized)
    ? values.filter(item => item !== normalized)
    : [...values, normalized].sort((left, right) => left.localeCompare(right));
}

function withSelectedFallbackOptions(
  options: readonly AgentSelectOption[],
  selectedValues: readonly string[],
  fallbackLabel: (value: string) => string = value => `当前：${value}`,
): AgentSelectOption[] {
  const optionValues = new Set(options.map(option => option.value));
  const fallbackOptions = uniqueStrings(selectedValues)
    .filter(value => !optionValues.has(value))
    .map(value => ({
      value,
      label: fallbackLabel(value),
    }));
  return [...fallbackOptions, ...options];
}

function optionSort(left: AgentSelectOption, right: AgentSelectOption): number {
  return left.label.localeCompare(right.label) || left.value.localeCompare(right.value);
}

function listFromScopedContext(value: Record<string, unknown> | undefined, key: string): string[] | undefined {
  const item = value?.[key];
  if (!Array.isArray(item)) return undefined;

  const strings = item.filter((entry): entry is string => typeof entry === "string" && entry.trim() !== "");
  return strings.length > 0 ? strings : undefined;
}

function scopedContextFromForm(form: AgentFormState): Record<string, unknown> | undefined {
  const catalogs = parseListText(form.catalogsText);
  const subjects = parseListText(form.subjectsText);
  if (!catalogs && !subjects) return undefined;

  return {
    ...(catalogs ? { catalogs } : {}),
    ...(subjects ? { subjects } : {}),
  };
}

function trimmedOptional(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function parsePositiveInteger(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;

  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("最大轮次必须是正整数");
  }

  return parsed;
}

function normalizeAgentVisibility(value: string | null | undefined): AgentVisibility {
  if (value === "enterprise" || value === "role") return value;
  return "private";
}

function formFromDetail(agent: AgentDetail): AgentFormState {
  const configuredTools = agent.tools?.length ? agent.tools : agent.tool_policy?.allowed;
  return {
    id: agent.agent_id,
    name: agent.name,
    nodeClass: agent.node_class || "gen_sql",
    status: agent.status || "draft",
    datasourceId: agent.datasource_id ?? "",
    artifactSlug: agent.artifact_slug ?? "",
    description: agent.description ?? "",
    promptTemplate: agent.prompt_template ?? agent.prompt_template_content ?? "",
    toolsText: listText(configuredTools),
    mcpText: listText(agent.mcp),
    skillsText: listText(agent.skills),
    catalogsText: listText(listFromScopedContext(agent.scoped_context, "catalogs")),
    subjectsText: listText(listFromScopedContext(agent.scoped_context, "subjects")),
    rulesText: listText(agent.rules),
    maxTurns: String(agent.max_turns || ""),
    visibility: normalizeAgentVisibility(agent.acl?.visibility),
    allowedRoleIds: [...(agent.acl?.allowed_roles ?? [])],
    allowedUserIds: [...(agent.acl?.allowed_user_ids ?? [])],
    toolPolicyMode: agent.tool_policy?.mode === "inherit" ? "inherit" : "allowlist",
    deniedToolsText: listText(agent.tool_policy?.denied),
    maxPermissionMode: agent.runtime_policy?.max_permission_mode === "dangerous"
      ? "dangerous"
      : agent.runtime_policy?.max_permission_mode === "auto" ? "auto" : "normal",
    allowSubagentDelegation: agent.runtime_policy?.allow_subagent_delegation ?? false,
    allowedSubagentIds: [...(agent.runtime_policy?.allowed_subagents ?? [])],
    defaultUserIds: [],
  };
}

function createInputFromForm(form: AgentFormState): CreateAgentInput {
  return {
    name: trimmedOptional(form.name),
    node_class: trimmedOptional(form.nodeClass) ?? "gen_sql",
    status: trimmedOptional(form.status) ?? "draft",
    datasource_id: trimmedOptional(form.datasourceId),
    artifact_slug: trimmedOptional(form.artifactSlug),
    description: trimmedOptional(form.description),
    prompt_template: trimmedOptional(form.promptTemplate),
    prompt_language: "en",
    prompt_version: "1.0",
    tools: parseListText(form.toolsText),
    mcp: parseListText(form.mcpText),
    skills: parseListText(form.skillsText),
    scoped_context: scopedContextFromForm(form),
    rules: parseListText(form.rulesText),
    max_turns: parsePositiveInteger(form.maxTurns) ?? 30,
    acl: {
      visibility: form.visibility,
      allowed_roles: form.allowedRoleIds,
      allowed_user_ids: form.allowedUserIds,
    },
    tool_policy: {
      mode: form.toolPolicyMode ?? "allowlist",
      allowed: form.toolPolicyMode !== "inherit" ? (parseListText(form.toolsText) ?? []) : [],
      denied: parseListText(form.deniedToolsText) ?? [],
    },
    runtime_policy: {
      max_permission_mode: form.maxPermissionMode ?? "normal",
      allow_subagent_delegation: Boolean(form.allowSubagentDelegation),
      allowed_subagents: form.allowSubagentDelegation ? form.allowedSubagentIds : [],
    },
  };
}

function policyInputFromForm(form: AgentFormState): AgentPolicy {
  return {
    tool_policy: {
      mode: form.toolPolicyMode ?? "allowlist",
      allowed: form.toolPolicyMode !== "inherit" ? (parseListText(form.toolsText) ?? []) : [],
      denied: parseListText(form.deniedToolsText) ?? [],
    },
    runtime_policy: {
      max_permission_mode: form.maxPermissionMode ?? "normal",
      allow_subagent_delegation: Boolean(form.allowSubagentDelegation),
      allowed_subagents: form.allowSubagentDelegation ? form.allowedSubagentIds : [],
    },
  };
}

function editInputFromForm(form: AgentFormState): EditAgentInput {
  return createInputFromForm(form);
}

function agentIdentifier(agent: AgentInfo | AgentDetail): string {
  return agent.agent_id;
}

function isBuiltinAgent(
  agent: AgentInfo | AgentDetail | null | undefined,
): agent is (AgentInfo | AgentDetail) & { source: "builtin" } {
  return agent?.source === "builtin";
}

function normalizeAgentList(result: AgentInfo[] | null): AgentInfo[] {
  return [...(result ?? [])].sort((left, right) =>
    left.name.localeCompare(right.name) || left.agent_id.localeCompare(right.agent_id)
  );
}

function datasourceOption(datasource: AdminDatasource): AgentSelectOption {
  const label = adminDatasourceLabel(datasource);
  return {
    value: datasource.name,
    label: datasource.is_default ? `${label}（默认）` : label,
    description: datasource.type ?? undefined,
  };
}

function artifactOption(artifact: AdminArtifact): AgentSelectOption {
  const manifest = artifact.manifest;
  const typeLabel = artifact.artifact_type === "report" ? "报表" : "仪表盘";
  return {
    value: manifest.slug,
    label: `${manifest.name || manifest.slug}（${typeLabel}）`,
    description: manifest.description || manifest.slug,
  };
}

function agentAclUserOption(user: AgentAclUserSummary): AgentSelectOption {
  const label = user.display_name?.trim() || user.user_id;
  const description = uniqueStrings([
    label === user.user_id ? "" : user.user_id,
    user.email ?? "",
    user.department ?? "",
    user.title ?? "",
  ]).join(" · ");
  return {
    value: user.user_id,
    label,
    description: description || undefined,
  };
}

function agentAclRoleOption(role: AgentAclRoleSummary): AgentSelectOption {
  return {
    value: role.role_id,
    label: role.name || role.role_id,
    description: role.description?.trim() || role.role_id,
  };
}

function toolOptionsFromCatalog(catalog: Record<string, string[]>): AgentSelectOption[] {
  return Object.entries(catalog).flatMap(([category, tools]) =>
    tools.map(tool => ({
      value: `${category}.${tool}`,
      label: tool,
      description: category,
    }))
  ).sort(optionSort);
}

function skillOptionsFromAgents(
  agents: readonly AgentInfo[],
  selectedAgent: AgentDetail | null,
  form: AgentFormState,
): AgentSelectOption[] {
  const known = uniqueStrings([
    ...(selectedAgent?.skills ?? []),
    ...(parseListText(form.skillsText) ?? []),
  ]);
  const ownerByAgent = new Map<string, string[]>();
  for (const skill of known) {
    ownerByAgent.set(skill, []);
  }
  if (selectedAgent?.skills?.length) {
    for (const skill of selectedAgent.skills) {
      ownerByAgent.set(skill, [selectedAgent.name]);
    }
  }
  return known.map((skill) => {
    const owners = ownerByAgent.get(skill) ?? [];
    return {
      value: skill,
      label: skill,
      description: owners.length ? `来自 ${owners.join("、")}` : agents.length ? "当前配置" : undefined,
    };
  }).sort(optionSort);
}

function countToolCatalogEntries(catalog: AgentToolsData | null): number {
  return Object.values(catalog?.tools ?? {}).reduce((total, tools) => total + tools.length, 0);
}

function countUseToolEntries(catalog: AgentUseToolsData | null): number {
  const defaults = catalog?.default_tools?.length ?? 0;
  const typed = Object.values(catalog?.tool_types ?? {}).reduce((total, item) => total + (item.tools?.length ?? 0), 0);
  return defaults + typed;
}

function mcpServerTarget(server: McpServerInfo): string {
  return server.command || server.url || server.cwd || "local";
}

function agentIdCandidate(raw: string): string {
  const sanitized = raw.replace(/[^A-Za-z0-9_-]/g, "_").replace(/^[^A-Za-z]+/, "");
  const candidate = sanitized || "custom_agent";
  return candidate.slice(0, 80);
}

function uniqueAgentId(baseId: string, existingAgents: readonly AgentInfo[]): string {
  const existingIds = new Set(existingAgents.map(agent => agent.agent_id));
  const candidate = agentIdCandidate(`${baseId}_custom`);
  if (!existingIds.has(candidate)) return candidate;

  for (let index = 2; index < 100; index += 1) {
    const suffix = `_${index}`;
    const next = `${candidate.slice(0, 80 - suffix.length)}${suffix}`;
    if (!existingIds.has(next)) return next;
  }

  return agentIdCandidate(`${baseId}_${Date.now()}`);
}

export function useAgentManager() {
  const connection = useConnection();
  const permission = usePermission();

  const agents = ref<AgentInfo[]>([]);
  const selectedAgent = ref<AgentDetail | null>(null);
  const nodeTypes = ref<AgentNodeType[]>([]);
  const toolCatalog = ref<AgentToolsData | null>(null);
  const selectedUseTools = ref<AgentUseToolsData | null>(null);
  const mcpServers = ref<McpServerInfo[]>([]);
  const mcpToolsByServer = ref<Record<string, string[]>>({});
  const datasources = ref<AdminDatasource[]>([]);
  const artifacts = ref<AdminArtifact[]>([]);
  const aclUsers = ref<AgentAclUserSummary[]>([]);
  const aclRoles = ref<AgentAclRoleSummary[]>([]);
  const enterpriseDefaultAgentId = shallowRef<string | null>(null);
  const form = ref<AgentFormState>(emptyForm());
  const formMode = shallowRef<AgentFormMode>("create");
  const loading = shallowRef(false);
  const detailLoading = shallowRef(false);
  const saving = shallowRef(false);
  const deleting = shallowRef(false);
  const nodeTypesLoading = shallowRef(false);
  const nodeTypesError = shallowRef<string | null>(null);
  const toolsLoading = shallowRef(false);
  const mcpCatalogLoading = shallowRef(false);
  const mcpCatalogLoaded = shallowRef(false);
  const mcpCatalogError = shallowRef<string | null>(null);
  const resourceCatalogLoading = shallowRef(false);
  const resourceCatalogError = shallowRef<string | null>(null);
  const aclDirectoryLoading = shallowRef(false);
  const aclDirectoryError = shallowRef<string | null>(null);
  const defaultPolicyLoading = shallowRef(false);
  const error = shallowRef<string | null>(null);
  const enterpriseRoutesUnavailable = shallowRef(false);

  const agentCount = computed(() => agents.value.length);
  const selectedAgentId = computed(() => selectedAgent.value?.agent_id ?? null);
  const selectedAgentName = computed(() => selectedAgent.value?.name ?? null);
  const selectedIsBuiltin = computed(() => isBuiltinAgent(selectedAgent.value));
  const selectedCanCloneBuiltin = computed(() =>
    selectedIsBuiltin.value
    && nodeTypes.value.some(item => item.node_class === selectedAgent.value?.node_class)
  );
  const toolCategoryCount = computed(() => Object.keys(toolCatalog.value?.tools ?? {}).length);
  const toolCount = computed(() => countToolCatalogEntries(toolCatalog.value));
  const selectedUseToolCount = computed(() => countUseToolEntries(selectedUseTools.value));
  const selectedTools = computed(() => parseListText(form.value.toolsText) ?? []);
  const deniedTools = computed(() => parseListText(form.value.deniedToolsText) ?? []);
  const selectedSkills = computed(() => parseListText(form.value.skillsText) ?? []);
  const selectedMcpNames = computed(() => new Set(parseListText(form.value.mcpText) ?? []));
  const datasourceOptions = computed(() =>
    withSelectedFallbackOptions(
      [...datasources.value]
        .sort((left, right) => left.name.localeCompare(right.name))
        .map(datasourceOption),
      form.value.datasourceId ? [form.value.datasourceId] : [],
    )
  );
  const artifactOptions = computed(() =>
    withSelectedFallbackOptions(
      artifacts.value.map(artifactOption).sort(optionSort),
      form.value.artifactSlug ? [form.value.artifactSlug] : [],
    )
  );
  const nodeClassOptions = computed(() =>
    withSelectedFallbackOptions(
      nodeTypes.value.map(item => ({
        value: item.node_class,
        label: item.label,
        description: item.description,
      })),
      form.value.nodeClass ? [form.value.nodeClass] : [],
    )
  );
  const toolOptions = computed(() => {
    const typeCatalog = Object.fromEntries(
      Object.entries(selectedUseTools.value?.tool_types ?? {})
        .map(([category, data]) => [category, data.tools ?? []] as const),
    );
    const baseOptions = toolOptionsFromCatalog(
      Object.keys(typeCatalog).length ? typeCatalog : toolCatalog.value?.tools ?? {},
    );
    const optionsWithDefaults = withSelectedFallbackOptions(
      baseOptions,
      selectedUseTools.value?.default_tools ?? [],
      value => `默认：${value}`,
    );
    return withSelectedFallbackOptions(
      optionsWithDefaults,
      [...selectedTools.value, ...deniedTools.value],
      value => `当前配置：${value}`,
    );
  });
  const skillOptions = computed(() => skillOptionsFromAgents(agents.value, selectedAgent.value, form.value));
  const canListMcpServers = computed(() => permission.hasPermission("mcp.server.list"));
  const canListMcpTools = computed(() => permission.hasPermission("mcp.server.tools"));
  const mcpServerOptions = computed<AgentMcpServerOption[]>(() => {
    const configuredOptions = [...mcpServers.value]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map((server) => ({
        name: server.name,
        type: server.type,
        target: mcpServerTarget(server),
        tools: mcpToolsByServer.value[server.name] ?? [],
        selected: selectedMcpNames.value.has(server.name),
        missing: false,
      }));
    if (!canListMcpServers.value || !mcpCatalogLoaded.value || mcpCatalogError.value) {
      return configuredOptions;
    }

    const configuredNames = new Set(configuredOptions.map(server => server.name));
    const missingOptions = [...selectedMcpNames.value]
      .filter(serverName => !configuredNames.has(serverName))
      .map(serverName => ({
        name: serverName,
        type: "missing",
        target: "Server 已不存在，请解除绑定",
        tools: [],
        selected: true,
        missing: true,
      }));
    return [...configuredOptions, ...missingOptions]
      .sort((left, right) => left.name.localeCompare(right.name));
  });
  const selectedMcpCount = computed(() => selectedMcpNames.value.size);
  const selectedMcpToolCount = computed(() =>
    [...selectedMcpNames.value].reduce((total, serverName) => total + (mcpToolsByServer.value[serverName]?.length ?? 0), 0)
  );
  const aclUserOptions = computed(() =>
    withSelectedFallbackOptions(
      aclUsers.value.map(agentAclUserOption).sort(optionSort),
      [...form.value.allowedUserIds, ...form.value.defaultUserIds],
    )
  );
  const aclRoleOptions = computed(() =>
    withSelectedFallbackOptions(
      aclRoles.value.map(agentAclRoleOption).sort(optionSort),
      form.value.allowedRoleIds,
    )
  );
  const subagentOptions = computed(() =>
    withSelectedFallbackOptions(
      agents.value
        .filter(agent => agent.agent_id !== selectedAgent.value?.agent_id)
        .map(agent => ({
          value: agent.agent_id,
          label: agent.name,
          description: agent.source === "builtin" ? "系统内置" : agent.node_class,
        }))
        .sort(optionSort),
      form.value.allowedSubagentIds,
    )
  );
  const canListAdminDatasources = computed(() => permission.hasPermission("module.admin.datasources"));
  const canListAdminArtifacts = computed(() => permission.hasPermission("module.admin.artifacts"));
  const canSubmitForm = computed(() => {
    if (saving.value) return false;
    if (formMode.value === "edit" && !form.value.id.trim()) return false;
    return Boolean(form.value.name.trim());
  });

  function agentRouteErrorMessage(err: unknown, fallback: string): string {
    if (err instanceof ApiResultError) {
      if (err.errorCode === "ENTERPRISE_ROUTE_DISABLED" || err.errorCode === "ENTERPRISE_LEGACY_API_DISABLED") {
        enterpriseRoutesUnavailable.value = true;
        return "当前企业 Agent 管理接口不可用，请确认后端企业接口已启用且当前用户具备管理权限。";
      }
      if (err.errorCode === "AGENT_DEFAULT_REQUIRES_PUBLISHED") {
        return "只有已发布的 Agent 才能分配默认用户，请先将状态切换为“已发布”。";
      }
      return err.message;
    }

    return fallback;
  }

  async function ensurePermissionsLoaded() {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
  }

  async function loadAgents() {
    loading.value = true;
    error.value = null;

    try {
      enterpriseRoutesUnavailable.value = false;
      agents.value = normalizeAgentList(await agentApi.list(connection.effectiveBase()));
      if (selectedAgent.value && !agents.value.some(agent => agentIdentifier(agent) === selectedAgent.value?.agent_id)) {
        selectedAgent.value = null;
        selectedUseTools.value = null;
        form.value = emptyForm();
        formMode.value = "create";
      }
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取 Agent 列表失败");
      console.error("读取 Agent 列表失败:", err);
      error.value = message;
      toast.error(message);
    } finally {
      loading.value = false;
    }
  }

  async function loadEnterpriseDefault() {
    defaultPolicyLoading.value = true;
    try {
      const result = await agentApi.enterpriseDefault(connection.effectiveBase());
      enterpriseDefaultAgentId.value = result?.default_agent_id ?? null;
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取企业默认 Agent 失败");
      console.error("读取企业默认 Agent 失败:", err);
      toast.error(message);
    } finally {
      defaultPolicyLoading.value = false;
    }
  }

  async function loadToolCatalog() {
    toolsLoading.value = true;

    try {
      toolCatalog.value = await agentApi.tools(connection.effectiveBase());
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取 Agent 工具目录失败");
      console.error("读取 Agent 工具目录失败:", err);
      toast.error(message);
    } finally {
      toolsLoading.value = false;
    }
  }

  async function loadNodeTypes() {
    nodeTypesLoading.value = true;
    nodeTypesError.value = null;

    try {
      nodeTypes.value = await agentApi.nodeTypes(connection.effectiveBase()) ?? [];
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取 Agent 节点类型失败");
      console.error("读取 Agent 节点类型失败:", err);
      nodeTypes.value = [];
      nodeTypesError.value = message;
      toast.error(message);
    } finally {
      nodeTypesLoading.value = false;
    }
  }

  async function loadMcpCatalog() {
    await ensurePermissionsLoaded();

    if (!canListMcpServers.value) {
      mcpServers.value = [];
      mcpToolsByServer.value = {};
      mcpCatalogLoaded.value = false;
      mcpCatalogError.value = null;
      return;
    }

    mcpCatalogLoading.value = true;
    mcpCatalogError.value = null;

    try {
      const result = await mcpApi.listServers(connection.effectiveBase());
      const servers = [...(result?.servers ?? [])].sort((left, right) => left.name.localeCompare(right.name));
      mcpServers.value = servers;
      mcpCatalogLoaded.value = true;

      if (canListMcpTools.value) {
        const toolEntries = await Promise.all(
          servers.map(async (server) => {
            try {
              const toolsResult = await mcpApi.listTools(connection.effectiveBase(), server.name);
              const toolNames = (toolsResult?.tools ?? [])
                .map((tool) => tool.name)
                .filter((name) => name.trim().length > 0)
                .sort((left, right) => left.localeCompare(right));
              return [server.name, toolNames] as const;
            } catch (err) {
              console.warn(`读取 MCP Server ${server.name} 工具失败`, err);
              return [server.name, []] as const;
            }
          })
        );
        mcpToolsByServer.value = Object.fromEntries(toolEntries);
      } else {
        mcpToolsByServer.value = Object.fromEntries(servers.map((server) => [server.name, []]));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "读取 MCP Server 失败";
      mcpServers.value = [];
      mcpToolsByServer.value = {};
      mcpCatalogLoaded.value = false;
      mcpCatalogError.value = message;
      console.error("读取 MCP Server 失败:", err);
      toast.error(message);
    } finally {
      mcpCatalogLoading.value = false;
    }
  }

  async function loadUseToolsForNodeClass(nodeClass = form.value.nodeClass) {
    const normalized = nodeClass.trim() || "gen_sql";
    try {
      selectedUseTools.value = await agentApi.useTools(connection.effectiveBase(), normalized);
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取节点工具参考失败");
      console.error("读取节点工具参考失败:", err);
      selectedUseTools.value = null;
      toast.error(message);
    }
  }

  async function loadResourceCatalogs() {
    await ensurePermissionsLoaded();

    if (!canListAdminDatasources.value && !canListAdminArtifacts.value) {
      datasources.value = [];
      artifacts.value = [];
      resourceCatalogError.value = null;
      return;
    }

    resourceCatalogLoading.value = true;
    resourceCatalogError.value = null;

    try {
      const [datasourceResult, artifactResult] = await Promise.all([
        canListAdminDatasources.value ? adminDatasourceApi.listDatasources() : Promise.resolve(null),
        canListAdminArtifacts.value ? adminArtifactApi.listArtifacts() : Promise.resolve(null),
      ]);
      datasources.value = [...(datasourceResult?.data ?? [])].sort((left, right) => left.name.localeCompare(right.name));
      artifacts.value = [...(artifactResult?.data ?? [])].sort((left, right) =>
        left.artifact_type.localeCompare(right.artifact_type)
        || left.manifest.name.localeCompare(right.manifest.name)
        || left.manifest.slug.localeCompare(right.manifest.slug)
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "读取 Agent 可选资源失败";
      datasources.value = [];
      artifacts.value = [];
      resourceCatalogError.value = message;
      console.error("读取 Agent 可选资源失败:", err);
      toast.error(message);
    } finally {
      resourceCatalogLoading.value = false;
    }
  }

  async function loadAclDirectory() {
    aclDirectoryLoading.value = true;
    aclDirectoryError.value = null;

    try {
      const [usersResult, rolesResult] = await Promise.all([
        agentApi.aclUsers(connection.effectiveBase()),
        agentApi.aclRoles(connection.effectiveBase()),
      ]);
      aclUsers.value = usersResult ?? [];
      aclRoles.value = rolesResult ?? [];
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取 Agent 可见用户和角色失败");
      aclUsers.value = [];
      aclRoles.value = [];
      aclDirectoryError.value = message;
      console.error("读取 Agent ACL 候选目录失败:", err);
      toast.error(message);
    } finally {
      aclDirectoryLoading.value = false;
    }
  }

  async function selectAgent(agentName: string | null) {
    if (!agentName) {
      selectedAgent.value = null;
      selectedUseTools.value = null;
      form.value = emptyForm();
      formMode.value = "create";
      return;
    }

    detailLoading.value = true;

    try {
      const detail = await agentApi.get(connection.effectiveBase(), agentName);
      selectedAgent.value = detail;
      if (detail) {
        form.value = formFromDetail(detail);
        form.value.defaultUserIds = await agentApi.defaultUsers(connection.effectiveBase(), detail.agent_id) ?? [];
        formMode.value = "edit";
        const nodeClass = detail.node_class || "gen_sql";
        if (!nodeTypes.value.length || nodeTypes.value.some(item => item.node_class === nodeClass)) {
          await loadUseToolsForNodeClass(nodeClass);
        } else {
          selectedUseTools.value = null;
        }
      } else {
        selectedUseTools.value = null;
      }
    } catch (err) {
      const message = agentRouteErrorMessage(err, "读取 Agent 详情失败");
      console.error("读取 Agent 详情失败:", err);
      toast.error(message);
    } finally {
      detailLoading.value = false;
    }
  }

  function startCreate() {
    selectedAgent.value = null;
    selectedUseTools.value = null;
    form.value = emptyForm();
    formMode.value = "create";
  }

  function startCreateFromSelectedBuiltin() {
    const source = selectedAgent.value;
    if (!isBuiltinAgent(source)) {
      toast.error("请选择一个系统内置 Agent 后再复制。");
      return false;
    }
    if (!nodeTypes.value.some(item => item.node_class === source.node_class)) {
      toast.error("当前系统内置 Agent 不支持复制为企业 Agent。");
      return false;
    }

    const agentId = uniqueAgentId(source.agent_id, agents.value);
    const defaultTools = selectedUseTools.value?.default_tools ?? [];
    form.value = {
      ...formFromDetail(source),
      id: "",
      name: agentId,
      nodeClass: source.node_class || source.agent_id,
      status: "draft",
      toolsText: source.tools?.length ? listText(source.tools) : listText(defaultTools),
      mcpText: "",
      visibility: "enterprise",
      allowedRoleIds: [],
      allowedUserIds: [],
      toolPolicyMode: "allowlist",
      deniedToolsText: "filesystem_tools.write_file\nfilesystem_tools.edit_file\nfilesystem_tools.delete_file\nbash_tools.*",
      maxPermissionMode: "normal",
      allowSubagentDelegation: false,
      allowedSubagentIds: [],
      defaultUserIds: [],
    };
    selectedAgent.value = null;
    formMode.value = "create";
    toast.success("已复制为企业 Agent 草稿，可选择 MCP 后保存。");
    return true;
  }

  function setMcpServerSelected(serverName: string, selected: boolean) {
    const normalized = serverName.trim();
    if (!normalized) return;

    const next = new Set(parseListText(form.value.mcpText) ?? []);
    if (selected) {
      next.add(normalized);
    } else {
      next.delete(normalized);
    }
    form.value.mcpText = [...next].sort((left, right) => left.localeCompare(right)).join("\n");
  }

  function toggleMcpServer(serverName: string) {
    setMcpServerSelected(serverName, !selectedMcpNames.value.has(serverName));
  }

  function setListFieldValues(field: AgentListFormField, values: readonly string[]) {
    form.value[field] = uniqueStrings(values).sort((left, right) => left.localeCompare(right)).join("\n");
  }

  function addListFieldValue(field: AgentListFormField, value: string) {
    const normalized = value.trim();
    if (!normalized) return;

    setListFieldValues(field, [...(parseListText(form.value[field]) ?? []), normalized]);
  }

  function toggleListFieldValue(field: AgentListFormField, value: string) {
    const normalized = value.trim();
    if (!normalized) return;

    const next = new Set(parseListText(form.value[field]) ?? []);
    if (next.has(normalized)) {
      next.delete(normalized);
    } else {
      next.add(normalized);
    }
    setListFieldValues(field, [...next]);
  }

  function toggleAclRole(roleId: string) {
    form.value.allowedRoleIds = toggleSelectedValue(form.value.allowedRoleIds, roleId);
  }

  function toggleAclUser(userId: string) {
    form.value.allowedUserIds = toggleSelectedValue(form.value.allowedUserIds, userId);
  }

  function toggleDefaultUser(userId: string) {
    form.value.defaultUserIds = toggleSelectedValue(form.value.defaultUserIds, userId);
  }

  function toggleAllowedSubagent(agentId: string) {
    form.value.allowedSubagentIds = toggleSelectedValue(form.value.allowedSubagentIds, agentId);
  }

  function applyDefaultTools() {
    const defaults = selectedUseTools.value?.default_tools ?? [];
    if (!defaults.length) {
      toast.error("当前节点类型没有返回默认工具。");
      return;
    }
    setListFieldValues("toolsText", defaults);
    toast.success("已应用默认工具");
  }

  async function saveForm(): Promise<boolean> {
    if (!canSubmitForm.value) return false;

    saving.value = true;

    try {
      const agentId = form.value.id.trim() || form.value.name.trim();
      const defaultUserIds = form.value.status === "published" ? form.value.defaultUserIds : [];
      if (formMode.value === "edit" && selectedIsBuiltin.value) {
        await agentApi.updateStatus(connection.effectiveBase(), agentId, form.value.status);
        await agentApi.updateAcl(connection.effectiveBase(), agentId, {
          visibility: form.value.visibility,
          allowed_roles: form.value.allowedRoleIds,
          allowed_user_ids: form.value.allowedUserIds,
        });
        await agentApi.updatePolicy(connection.effectiveBase(), agentId, policyInputFromForm(form.value));
        await agentApi.updateDefaultUsers(connection.effectiveBase(), agentId, defaultUserIds);
        toast.success("内置 Agent 企业策略已保存");
      } else if (formMode.value === "edit") {
        await agentApi.edit(connection.effectiveBase(), agentId, editInputFromForm(form.value));
        await agentApi.updateDefaultUsers(connection.effectiveBase(), agentId, defaultUserIds);
        toast.success("Agent 已保存");
      } else {
        await agentApi.create(connection.effectiveBase(), agentId, createInputFromForm(form.value));
        await agentApi.updateDefaultUsers(connection.effectiveBase(), agentId, defaultUserIds);
        toast.success("Agent 已创建");
      }

      const nextSelection = agentId;
      await loadAgents();
      await selectAgent(nextSelection);
      return true;
    } catch (err) {
      const message = agentRouteErrorMessage(
        err,
        err instanceof Error ? err.message : "Agent 保存失败",
      );
      console.error("保存 Agent 失败:", err);
      toast.error(message);
      return false;
    } finally {
      saving.value = false;
    }
  }

  async function setEnterpriseDefault(agentId: string | null) {
    defaultPolicyLoading.value = true;
    try {
      const result = await agentApi.updateEnterpriseDefault(connection.effectiveBase(), agentId);
      enterpriseDefaultAgentId.value = result?.default_agent_id ?? null;
      toast.success(agentId ? "企业默认 Agent 已更新" : "已清除企业默认 Agent");
    } catch (err) {
      const message = agentRouteErrorMessage(err, "更新企业默认 Agent 失败");
      console.error("更新企业默认 Agent 失败:", err);
      toast.error(message);
    } finally {
      defaultPolicyLoading.value = false;
    }
  }

  async function deleteAgent(agentId: string) {
    const target = agents.value.find(agent => agent.agent_id === agentId)
      ?? (selectedAgent.value?.agent_id === agentId ? selectedAgent.value : undefined);
    if (isBuiltinAgent(target)) {
      toast.error("系统内置 Agent 为只读，不能删除。");
      return;
    }

    deleting.value = true;

    try {
      await agentApi.delete(connection.effectiveBase(), agentId);
      toast.success("Agent 已删除");
      await loadAgents();
      if (selectedAgent.value?.agent_id === agentId) {
        startCreate();
      }
    } catch (err) {
      const message = agentRouteErrorMessage(err, "删除 Agent 失败");
      console.error("删除 Agent 失败:", err);
      toast.error(message);
    } finally {
      deleting.value = false;
    }
  }

  function toolCatalogEntries(): Array<[string, string[]]> {
    return Object.entries(toolCatalog.value?.tools ?? {});
  }

  function useToolTypeEntries(): Array<[string, string[]]> {
    return Object.entries(selectedUseTools.value?.tool_types ?? {}).map(([name, data]) => [name, data.tools ?? []]);
  }

  return {
    agents: readonly(agents),
    selectedAgent: readonly(selectedAgent),
    nodeTypes: readonly(nodeTypes),
    selectedUseTools: readonly(selectedUseTools),
    mcpServers: readonly(mcpServers),
    mcpToolsByServer: readonly(mcpToolsByServer),
    datasources: readonly(datasources),
    artifacts: readonly(artifacts),
    aclUsers: readonly(aclUsers),
    aclRoles: readonly(aclRoles),
    enterpriseDefaultAgentId: readonly(enterpriseDefaultAgentId),
    toolCatalog: readonly(toolCatalog),
    form,
    formMode: readonly(formMode),
    loading: readonly(loading),
    detailLoading: readonly(detailLoading),
    saving: readonly(saving),
    deleting: readonly(deleting),
    nodeTypesLoading: readonly(nodeTypesLoading),
    nodeTypesError: readonly(nodeTypesError),
    toolsLoading: readonly(toolsLoading),
    mcpCatalogLoading: readonly(mcpCatalogLoading),
    mcpCatalogError: readonly(mcpCatalogError),
    resourceCatalogLoading: readonly(resourceCatalogLoading),
    resourceCatalogError: readonly(resourceCatalogError),
    aclDirectoryLoading: readonly(aclDirectoryLoading),
    aclDirectoryError: readonly(aclDirectoryError),
    defaultPolicyLoading: readonly(defaultPolicyLoading),
    error: readonly(error),
    enterpriseRoutesUnavailable: readonly(enterpriseRoutesUnavailable),
    agentCount,
    selectedAgentId,
    selectedAgentName,
    selectedIsBuiltin,
    selectedCanCloneBuiltin,
    toolCategoryCount,
    toolCount,
    selectedUseToolCount,
    selectedTools,
    deniedTools,
    selectedSkills,
    datasourceOptions,
    artifactOptions,
    nodeClassOptions,
    toolOptions,
    skillOptions,
    mcpServerOptions,
    aclUserOptions,
    aclRoleOptions,
    subagentOptions,
    selectedMcpCount,
    selectedMcpToolCount,
    canSubmitForm,
    loadAgents,
    loadEnterpriseDefault,
    loadNodeTypes,
    loadToolCatalog,
    loadMcpCatalog,
    loadResourceCatalogs,
    loadAclDirectory,
    loadUseToolsForNodeClass,
    selectAgent,
    startCreate,
    startCreateFromSelectedBuiltin,
    setMcpServerSelected,
    toggleMcpServer,
    addListFieldValue,
    toggleListFieldValue,
    toggleAclRole,
    toggleAclUser,
    toggleDefaultUser,
    toggleAllowedSubagent,
    applyDefaultTools,
    saveForm,
    setEnterpriseDefault,
    deleteAgent,
    isBuiltinAgent,
    toolCatalogEntries,
    useToolTypeEntries,
  };
}

export type AgentManagerController = ReturnType<typeof useAgentManager>;

export const agentManagerInternals = {
  createInputFromForm,
  editInputFromForm,
  parseListText,
  parsePositiveInteger,
  normalizeAgentVisibility,
  normalizeAgentList,
  agentIdentifier,
  scopedContextFromForm,
  countToolCatalogEntries,
  countUseToolEntries,
  uniqueAgentId,
  isRecord,
};

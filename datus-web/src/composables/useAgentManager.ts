import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { agentApi, mcpApi } from "@/lib/api";
import { ApiResultError } from "@/lib/chat";
import type {
  AgentDetail,
  AgentInfo,
  AgentToolsData,
  AgentUseToolsData,
  CreateAgentInput,
  EditAgentInput,
  McpServerInfo,
} from "@/types";

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
}

export type AgentFormMode = "create" | "edit";

export interface AgentMcpServerOption {
  name: string;
  type: string;
  target: string;
  tools: string[];
  selected: boolean;
}

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
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseListText(value: string): string[] | undefined {
  const items = value
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean);

  return items.length > 0 ? items : undefined;
}

function listText(value: string[] | undefined): string {
  return value?.join("\n") ?? "";
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

function formFromDetail(agent: AgentDetail): AgentFormState {
  return {
    id: agent.agent_id,
    name: agent.name,
    nodeClass: agent.node_class || "gen_sql",
    status: agent.status || "draft",
    datasourceId: agent.datasource_id ?? "",
    artifactSlug: agent.artifact_slug ?? "",
    description: agent.description ?? "",
    promptTemplate: agent.prompt_template ?? agent.prompt_template_content ?? "",
    toolsText: listText(agent.tools),
    mcpText: listText(agent.mcp),
    skillsText: listText(agent.skills),
    catalogsText: listText(listFromScopedContext(agent.scoped_context, "catalogs")),
    subjectsText: listText(listFromScopedContext(agent.scoped_context, "subjects")),
    rulesText: listText(agent.rules),
    maxTurns: String(agent.max_turns || ""),
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

  const agents = ref<AgentInfo[]>([]);
  const selectedAgent = ref<AgentDetail | null>(null);
  const toolCatalog = ref<AgentToolsData | null>(null);
  const selectedUseTools = ref<AgentUseToolsData | null>(null);
  const mcpServers = ref<McpServerInfo[]>([]);
  const mcpToolsByServer = ref<Record<string, string[]>>({});
  const form = ref<AgentFormState>(emptyForm());
  const formMode = shallowRef<AgentFormMode>("create");
  const loading = shallowRef(false);
  const detailLoading = shallowRef(false);
  const saving = shallowRef(false);
  const deleting = shallowRef(false);
  const toolsLoading = shallowRef(false);
  const mcpCatalogLoading = shallowRef(false);
  const mcpCatalogError = shallowRef<string | null>(null);
  const error = shallowRef<string | null>(null);
  const enterpriseRoutesUnavailable = shallowRef(false);

  const agentCount = computed(() => agents.value.length);
  const selectedAgentId = computed(() => selectedAgent.value?.agent_id ?? null);
  const selectedAgentName = computed(() => selectedAgent.value?.name ?? null);
  const selectedIsBuiltin = computed(() => isBuiltinAgent(selectedAgent.value));
  const toolCategoryCount = computed(() => Object.keys(toolCatalog.value?.tools ?? {}).length);
  const toolCount = computed(() => countToolCatalogEntries(toolCatalog.value));
  const selectedUseToolCount = computed(() => countUseToolEntries(selectedUseTools.value));
  const selectedMcpNames = computed(() => new Set(parseListText(form.value.mcpText) ?? []));
  const mcpServerOptions = computed<AgentMcpServerOption[]>(() =>
    [...mcpServers.value]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map((server) => ({
        name: server.name,
        type: server.type,
        target: mcpServerTarget(server),
        tools: mcpToolsByServer.value[server.name] ?? [],
        selected: selectedMcpNames.value.has(server.name),
      }))
  );
  const selectedMcpCount = computed(() => selectedMcpNames.value.size);
  const selectedMcpToolCount = computed(() =>
    [...selectedMcpNames.value].reduce((total, serverName) => total + (mcpToolsByServer.value[serverName]?.length ?? 0), 0)
  );
  const canSubmitForm = computed(() => {
    if (saving.value) return false;
    if (formMode.value === "edit" && selectedIsBuiltin.value) return false;
    if (formMode.value === "edit" && !form.value.id.trim()) return false;
    return Boolean(form.value.name.trim());
  });

  function agentRouteErrorMessage(err: unknown, fallback: string): string {
    if (err instanceof ApiResultError) {
      if (err.errorCode === "ENTERPRISE_ROUTE_DISABLED" || err.errorCode === "ENTERPRISE_LEGACY_API_DISABLED") {
        enterpriseRoutesUnavailable.value = true;
        return "当前企业 Agent 管理接口不可用，请确认后端企业接口已启用且当前用户具备管理权限。";
      }
      return err.message;
    }

    return fallback;
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

  async function loadMcpCatalog() {
    mcpCatalogLoading.value = true;
    mcpCatalogError.value = null;

    try {
      const result = await mcpApi.listServers(connection.effectiveBase());
      const servers = [...(result?.servers ?? [])].sort((left, right) => left.name.localeCompare(right.name));
      mcpServers.value = servers;

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
    } catch (err) {
      const message = err instanceof Error ? err.message : "读取 MCP Server 失败";
      mcpServers.value = [];
      mcpToolsByServer.value = {};
      mcpCatalogError.value = message;
      console.error("读取 MCP Server 失败:", err);
      toast.error(message);
    } finally {
      mcpCatalogLoading.value = false;
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
      selectedUseTools.value = await agentApi.useTools(connection.effectiveBase(), detail?.node_class || "gen_sql");
      if (detail) {
        form.value = formFromDetail(detail);
        formMode.value = "edit";
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

  async function saveForm(): Promise<boolean> {
    if (formMode.value === "edit" && selectedIsBuiltin.value) {
      toast.error("系统内置 Agent 为只读，不能在管理页保存。");
      return false;
    }
    if (!canSubmitForm.value) return false;

    saving.value = true;

    try {
      const agentId = form.value.id.trim() || form.value.name.trim();
      if (formMode.value === "edit") {
        await agentApi.edit(connection.effectiveBase(), agentId, editInputFromForm(form.value));
        toast.success("Agent 已保存");
      } else {
        await agentApi.create(connection.effectiveBase(), agentId, createInputFromForm(form.value));
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
    selectedUseTools: readonly(selectedUseTools),
    mcpServers: readonly(mcpServers),
    mcpToolsByServer: readonly(mcpToolsByServer),
    toolCatalog: readonly(toolCatalog),
    form,
    formMode: readonly(formMode),
    loading: readonly(loading),
    detailLoading: readonly(detailLoading),
    saving: readonly(saving),
    deleting: readonly(deleting),
    toolsLoading: readonly(toolsLoading),
    mcpCatalogLoading: readonly(mcpCatalogLoading),
    mcpCatalogError: readonly(mcpCatalogError),
    error: readonly(error),
    enterpriseRoutesUnavailable: readonly(enterpriseRoutesUnavailable),
    agentCount,
    selectedAgentId,
    selectedAgentName,
    selectedIsBuiltin,
    toolCategoryCount,
    toolCount,
    selectedUseToolCount,
    mcpServerOptions,
    selectedMcpCount,
    selectedMcpToolCount,
    canSubmitForm,
    loadAgents,
    loadToolCatalog,
    loadMcpCatalog,
    selectAgent,
    startCreate,
    startCreateFromSelectedBuiltin,
    setMcpServerSelected,
    toggleMcpServer,
    saveForm,
    deleteAgent,
    isBuiltinAgent,
    toolCatalogEntries,
    useToolTypeEntries,
  };
}

export const agentManagerInternals = {
  createInputFromForm,
  editInputFromForm,
  parseListText,
  parsePositiveInteger,
  normalizeAgentList,
  agentIdentifier,
  scopedContextFromForm,
  countToolCatalogEntries,
  countUseToolEntries,
  uniqueAgentId,
  isRecord,
};

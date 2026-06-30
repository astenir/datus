import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { agentApi } from "@/lib/api";
import { ApiResultError } from "@/lib/chat";
import type {
  AgentDetail,
  AgentInfo,
  AgentToolsData,
  AgentUseToolsData,
  CreateAgentInput,
  EditAgentInput,
} from "@/types";

export interface AgentFormState {
  id: string;
  name: string;
  nodeClass: string;
  status: string;
  description: string;
  promptTemplate: string;
  toolsText: string;
  catalogsText: string;
  subjectsText: string;
  rulesText: string;
  maxTurns: string;
}

export type AgentFormMode = "create" | "edit";

function emptyForm(): AgentFormState {
  return {
    id: "",
    name: "",
    nodeClass: "gen_sql",
    status: "draft",
    description: "",
    promptTemplate: "",
    toolsText: "",
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
    description: agent.description ?? "",
    promptTemplate: agent.prompt_template ?? "",
    toolsText: listText(agent.tools),
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
    description: trimmedOptional(form.description),
    prompt_template: trimmedOptional(form.promptTemplate),
    prompt_language: "en",
    prompt_version: "1.0",
    tools: parseListText(form.toolsText),
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

export function useAgentManager() {
  const connection = useConnection();

  const agents = ref<AgentInfo[]>([]);
  const selectedAgent = ref<AgentDetail | null>(null);
  const toolCatalog = ref<AgentToolsData | null>(null);
  const selectedUseTools = ref<AgentUseToolsData | null>(null);
  const form = ref<AgentFormState>(emptyForm());
  const formMode = shallowRef<AgentFormMode>("create");
  const loading = shallowRef(false);
  const detailLoading = shallowRef(false);
  const saving = shallowRef(false);
  const deleting = shallowRef(false);
  const toolsLoading = shallowRef(false);
  const error = shallowRef<string | null>(null);
  const enterpriseRoutesUnavailable = shallowRef(false);

  const agentCount = computed(() => agents.value.length);
  const selectedAgentId = computed(() => selectedAgent.value?.agent_id ?? null);
  const selectedAgentName = computed(() => selectedAgent.value?.name ?? null);
  const toolCategoryCount = computed(() => Object.keys(toolCatalog.value?.tools ?? {}).length);
  const toolCount = computed(() => countToolCatalogEntries(toolCatalog.value));
  const selectedUseToolCount = computed(() => countUseToolEntries(selectedUseTools.value));
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

  async function saveForm(): Promise<boolean> {
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
    toolCatalog: readonly(toolCatalog),
    form,
    formMode: readonly(formMode),
    loading: readonly(loading),
    detailLoading: readonly(detailLoading),
    saving: readonly(saving),
    deleting: readonly(deleting),
    toolsLoading: readonly(toolsLoading),
    error: readonly(error),
    enterpriseRoutesUnavailable: readonly(enterpriseRoutesUnavailable),
    agentCount,
    selectedAgentId,
    selectedAgentName,
    toolCategoryCount,
    toolCount,
    selectedUseToolCount,
    canSubmitForm,
    loadAgents,
    loadToolCatalog,
    selectAgent,
    startCreate,
    saveForm,
    deleteAgent,
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
  isRecord,
};

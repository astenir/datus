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
  type: string;
  description: string;
  promptTemplate: string;
  toolsText: string;
  catalogsText: string;
  subjectsText: string;
  rulesText: string;
  maxTurns: string;
  workspaceRoot: string;
}

export type AgentFormMode = "create" | "edit";

function emptyForm(): AgentFormState {
  return {
    id: "",
    name: "",
    type: "",
    description: "",
    promptTemplate: "",
    toolsText: "",
    catalogsText: "",
    subjectsText: "",
    rulesText: "",
    maxTurns: "",
    workspaceRoot: "",
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
    id: agent.name,
    name: agent.name,
    type: agent.type ?? "",
    description: "",
    promptTemplate: agent.system_prompt ?? agent.config_yaml ?? "",
    toolsText: listText(agent.tools),
    catalogsText: listText(agent.catalogs),
    subjectsText: listText(agent.subjects),
    rulesText: listText(agent.rules),
    maxTurns: "",
    workspaceRoot: "",
  };
}

function createInputFromForm(form: AgentFormState): CreateAgentInput {
  return {
    name: form.name.trim(),
    type: trimmedOptional(form.type),
    description: trimmedOptional(form.description),
    prompt_template: trimmedOptional(form.promptTemplate),
    tools: parseListText(form.toolsText),
    catalogs: parseListText(form.catalogsText),
    subjects: parseListText(form.subjectsText),
    rules: parseListText(form.rulesText),
    max_turns: parsePositiveInteger(form.maxTurns),
    workspace_root: trimmedOptional(form.workspaceRoot),
  };
}

function editInputFromForm(form: AgentFormState): EditAgentInput {
  return {
    id: form.id.trim() || form.name.trim(),
    name: trimmedOptional(form.name),
    description: trimmedOptional(form.description),
    system_prompt: trimmedOptional(form.promptTemplate),
    tools: parseListText(form.toolsText),
    catalogs: parseListText(form.catalogsText),
    subjects: parseListText(form.subjectsText),
    rules: parseListText(form.rulesText),
    max_turns: parsePositiveInteger(form.maxTurns),
    workspace_root: trimmedOptional(form.workspaceRoot),
  };
}

function normalizeAgentList(result: { agents?: AgentInfo[] } | null): AgentInfo[] {
  return [...(result?.agents ?? [])].sort((left, right) => left.name.localeCompare(right.name));
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
  const legacyRoutesDisabled = shallowRef(false);

  const agentCount = computed(() => agents.value.length);
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
        legacyRoutesDisabled.value = true;
        return "当前企业后端已禁用 legacy Agent 配置接口，请等待企业 Agent 管理接口接入。";
      }
      return err.message;
    }

    return fallback;
  }

  async function loadAgents() {
    loading.value = true;
    error.value = null;

    try {
      legacyRoutesDisabled.value = false;
      agents.value = normalizeAgentList(await agentApi.list(connection.effectiveBase()));
      if (selectedAgent.value && !agents.value.some(agent => agent.name === selectedAgent.value?.name)) {
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
      selectedUseTools.value = await agentApi.useTools(connection.effectiveBase(), detail?.type || agentName);
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

  async function saveForm() {
    if (!canSubmitForm.value) return;

    saving.value = true;

    try {
      if (formMode.value === "edit") {
        await agentApi.edit(connection.effectiveBase(), editInputFromForm(form.value));
        toast.success("Agent 已保存");
      } else {
        await agentApi.create(connection.effectiveBase(), createInputFromForm(form.value));
        toast.success("Agent 已创建");
      }

      const nextSelection = form.value.name.trim();
      await loadAgents();
      await selectAgent(nextSelection);
    } catch (err) {
      const message = agentRouteErrorMessage(
        err,
        err instanceof Error ? err.message : "Agent 保存失败",
      );
      console.error("保存 Agent 失败:", err);
      toast.error(message);
    } finally {
      saving.value = false;
    }
  }

  async function deleteAgent(agentName: string) {
    deleting.value = true;

    try {
      await agentApi.delete(connection.effectiveBase(), agentName);
      toast.success("Agent 已删除");
      await loadAgents();
      if (selectedAgent.value?.name === agentName) {
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
    legacyRoutesDisabled: readonly(legacyRoutesDisabled),
    agentCount,
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
  countToolCatalogEntries,
  countUseToolEntries,
  isRecord,
};

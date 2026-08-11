import {
  computed,
  getCurrentScope,
  onScopeDispose,
  readonly,
  ref,
  shallowRef,
} from "vue";
import { toast } from "vue-sonner";

import { meApi } from "@/lib/api";
import {
  clearPersonalMcpDisplayNames,
  setPersonalMcpDisplayNames,
} from "@/lib/personal-mcp-display";
import { HttpError } from "@/lib/request";
import type {
  ApiResponse,
  PersonalMcpConnectivityResult,
  PersonalMcpOptions,
  PersonalMcpSummary,
  PersonalMcpToolSummary,
  UpsertPersonalMcpInput,
} from "@/types/profile";

const MCP_CONNECTION_FAILURE = "MCP 连接失败，请检查配置和网络后重试";

function defaultOptions(): PersonalMcpOptions {
  return {
    enabled: false,
    allowed_hosts: [],
    max_servers_per_user: 0,
    max_selected_per_session: 0,
  };
}

function resultData<T>(response: ApiResponse<T>, fallback: T): T {
  if (!response.success) {
    throw new Error(response.errorMessage || response.errorCode || "请求失败");
  }
  return response.data ?? fallback;
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function personalMcpInUseCount(error: unknown): Promise<number | null> {
  if (!(error instanceof HttpError) || error.status !== 409 || !error.response) return null;

  try {
    const payload = await error.response.clone().json() as unknown;
    if (!isRecord(payload) || !isRecord(payload.detail)) return null;
    if (payload.detail.code !== "PERSONAL_MCP_SERVER_IN_USE") return null;
    return typeof payload.detail.session_count === "number" ? payload.detail.session_count : null;
  } catch {
    return null;
  }
}

// 个人 MCP 状态在模块级共享：会话工作区（会话内 MCP 选择器）与 MCP 管理页各自调用
// usePersonalMcp() 时读写同一份 servers/options，管理页的新增、启用、删除会立即
// 反映到会话选择列表，无需整页刷新。dispose 通过实例计数保护：只要还有存活实例
// （例如 MCP 管理页随 Tab 切换卸载，但工作区仍在），就不会中止请求或清空共享状态。
const loading = shallowRef(false);
const saving = shallowRef(false);
const testingId = shallowRef<string | null>(null);
const toolsLoadingId = shallowRef<string | null>(null);
const bindingLoading = shallowRef(false);
const error = shallowRef<string | null>(null);
const options = ref<PersonalMcpOptions>(defaultOptions());
const servers = ref<PersonalMcpSummary[]>([]);
const tools = ref<Record<string, PersonalMcpToolSummary[]>>({});
const selectedIds = ref<string[]>([]);
const selectionLocked = shallowRef(false);
const boundSessionId = shallowRef<string | null>(null);

let loadController: AbortController | null = null;
let toolsController: AbortController | null = null;
let testController: AbortController | null = null;
let bindingController: AbortController | null = null;
let instanceCount = 0;

function dispose(): void {
  instanceCount = Math.max(0, instanceCount - 1);
  if (instanceCount > 0) return;

  loadController?.abort();
  toolsController?.abort();
  testController?.abort();
  bindingController?.abort();
  loadController = null;
  toolsController = null;
  testController = null;
  bindingController = null;
  loading.value = false;
  saving.value = false;
  testingId.value = null;
  toolsLoadingId.value = null;
  bindingLoading.value = false;
  error.value = null;
  options.value = defaultOptions();
  servers.value = [];
  tools.value = {};
  selectedIds.value = [];
  selectionLocked.value = false;
  boundSessionId.value = null;
  clearPersonalMcpDisplayNames();
}

export function usePersonalMcp() {
  instanceCount += 1;
  if (getCurrentScope()) onScopeDispose(dispose);

  const enabledServers = computed(() => servers.value.filter(server => server.enabled));
  const isAvailable = computed(() => options.value.enabled && options.value.allowed_hosts.length > 0);
  const maxSelected = computed(() => options.value.max_selected_per_session);
  const selectedServers = computed(() => {
    const selected = new Set(selectedIds.value);
    return servers.value.filter(server => selected.has(server.id));
  });

  async function load(): Promise<void> {
    loadController?.abort();
    const controller = new AbortController();
    loadController = controller;
    loading.value = true;
    error.value = null;

    try {
      const [optionsResult, serversResult] = await Promise.all([
        meApi.personalMcpOptions(controller.signal),
        meApi.personalMcpServers(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      options.value = resultData(optionsResult, defaultOptions());
      servers.value = resultData(serversResult, []);
      // 服务列表携带 MCP 名称，供工具卡片 / 权限请求把 personal_<id> 别名还原为名称。
      setPersonalMcpDisplayNames(servers.value.map(server => ({
        id: server.id,
        displayName: server.display_name,
      })));
    } catch (loadError) {
      if (isAbortError(loadError) || controller.signal.aborted) return;
      console.error("加载个人 MCP 失败:", loadError);
      error.value = "加载个人 MCP 失败";
      toast.error("加载个人 MCP 失败");
    } finally {
      if (loadController === controller) {
        loadController = null;
        loading.value = false;
      }
    }
  }

  async function createServer(input: UpsertPersonalMcpInput): Promise<PersonalMcpSummary | null> {
    saving.value = true;
    error.value = null;
    try {
      const server = resultData<PersonalMcpSummary | null>(await meApi.createPersonalMcp(input), null);
      if (server) servers.value = [...servers.value, server];
      toast.success("个人 MCP 已添加");
      return server;
    } catch (saveError) {
      console.error("添加个人 MCP 失败:", saveError);
      error.value = "添加个人 MCP 失败";
      toast.error("添加个人 MCP 失败");
      throw saveError;
    } finally {
      saving.value = false;
    }
  }

  async function updateServer(
    id: string,
    input: UpsertPersonalMcpInput,
  ): Promise<PersonalMcpSummary | null> {
    saving.value = true;
    error.value = null;
    try {
      const server = resultData<PersonalMcpSummary | null>(await meApi.updatePersonalMcp(id, input), null);
      if (server) {
        servers.value = servers.value.map(item => item.id === id ? server : item);
        tools.value = { ...tools.value, [id]: [] };
      }
      toast.success("个人 MCP 已更新");
      return server;
    } catch (saveError) {
      console.error("更新个人 MCP 失败:", saveError);
      error.value = "更新个人 MCP 失败";
      toast.error("更新个人 MCP 失败");
      throw saveError;
    } finally {
      saving.value = false;
    }
  }

  async function deleteServer(id: string): Promise<boolean> {
    saving.value = true;
    error.value = null;
    try {
      const result = resultData(await meApi.deletePersonalMcp(id), { deleted: false });
      if (!result.deleted) return false;
      servers.value = servers.value.filter(server => server.id !== id);
      selectedIds.value = selectedIds.value.filter(selectedId => selectedId !== id);
      const nextTools = { ...tools.value };
      delete nextTools[id];
      tools.value = nextTools;
      toast.success("个人 MCP 已删除");
      return true;
    } catch (deleteError) {
      const sessionCount = await personalMcpInUseCount(deleteError);
      const message = sessionCount === null
        ? "删除个人 MCP 失败"
        : `该 MCP 仍被 ${sessionCount} 个会话引用，暂时不能删除`;
      console.error("删除个人 MCP 失败:", deleteError);
      error.value = message;
      toast.error(message);
      return false;
    } finally {
      saving.value = false;
    }
  }

  async function testServer(id: string): Promise<PersonalMcpConnectivityResult | null> {
    testController?.abort();
    const controller = new AbortController();
    testController = controller;
    testingId.value = id;
    try {
      const result = resultData<PersonalMcpConnectivityResult | null>(
        await meApi.testPersonalMcp(id, controller.signal),
        null,
      );
      if (controller.signal.aborted || !result) return null;
      if (result.connected) {
        toast.success("MCP 连接正常");
        return { ...result, message: "连接正常" };
      }
      toast.error(MCP_CONNECTION_FAILURE);
      return { ...result, message: MCP_CONNECTION_FAILURE };
    } catch (testError) {
      if (isAbortError(testError) || controller.signal.aborted) return null;
      console.error("测试个人 MCP 失败:", testError);
      toast.error(MCP_CONNECTION_FAILURE);
      return null;
    } finally {
      if (testController === controller) {
        testController = null;
        testingId.value = null;
      }
    }
  }

  async function loadTools(id: string): Promise<readonly PersonalMcpToolSummary[]> {
    toolsController?.abort();
    const controller = new AbortController();
    toolsController = controller;
    toolsLoadingId.value = id;
    try {
      const result = resultData(await meApi.personalMcpTools(id, controller.signal), []);
      if (controller.signal.aborted) return [];
      tools.value = { ...tools.value, [id]: result };
      return result;
    } catch (toolsError) {
      if (isAbortError(toolsError) || controller.signal.aborted) return [];
      console.error("加载个人 MCP 工具失败:", toolsError);
      tools.value = { ...tools.value, [id]: [] };
      toast.error(MCP_CONNECTION_FAILURE);
      return [];
    } finally {
      if (toolsController === controller) {
        toolsController = null;
        toolsLoadingId.value = null;
      }
    }
  }

  function toggleSelection(id: string): boolean {
    if (selectionLocked.value) return false;
    const server = servers.value.find(item => item.id === id);
    if (!server?.enabled) return false;

    if (selectedIds.value.includes(id)) {
      selectedIds.value = selectedIds.value.filter(selectedId => selectedId !== id);
      return true;
    }
    if (selectedIds.value.length >= maxSelected.value) {
      toast.error(`每个会话最多选择 ${maxSelected.value} 个个人 MCP`);
      return false;
    }
    selectedIds.value = [...selectedIds.value, id];
    return true;
  }

  async function loadSessionBinding(sessionId: string): Promise<void> {
    bindingController?.abort();
    const controller = new AbortController();
    bindingController = controller;
    bindingLoading.value = true;
    selectionLocked.value = true;
    boundSessionId.value = sessionId;
    selectedIds.value = [];
    try {
      const result = resultData(
        await meApi.personalMcpSessionBinding(sessionId, controller.signal),
        { session_id: sessionId, servers: [] },
      );
      if (controller.signal.aborted) return;
      selectedIds.value = result.servers.map(server => server.mcp_id);
      // 会话绑定是权威来源（服务可能已重命名），以绑定返回的 MCP 名称为准。
      setPersonalMcpDisplayNames(result.servers.map(server => ({
        id: server.mcp_id,
        displayName: server.display_name,
      })));
    } catch (bindingError) {
      if (isAbortError(bindingError) || controller.signal.aborted) return;
      console.error("恢复会话个人 MCP 选择失败:", bindingError);
      error.value = "恢复会话个人 MCP 选择失败";
      toast.error("恢复会话个人 MCP 选择失败");
    } finally {
      if (bindingController === controller) {
        bindingController = null;
        bindingLoading.value = false;
      }
    }
  }

  function resetDraftSelection(): void {
    bindingController?.abort();
    bindingController = null;
    bindingLoading.value = false;
    selectionLocked.value = false;
    boundSessionId.value = null;
    selectedIds.value = [];
    clearPersonalMcpDisplayNames();
  }

  return {
    loading: readonly(loading),
    saving: readonly(saving),
    testingId: readonly(testingId),
    toolsLoadingId: readonly(toolsLoadingId),
    bindingLoading: readonly(bindingLoading),
    error: readonly(error),
    options: readonly(options),
    servers: readonly(servers),
    tools: readonly(tools),
    selectedIds: readonly(selectedIds),
    selectionLocked: readonly(selectionLocked),
    boundSessionId: readonly(boundSessionId),
    enabledServers,
    selectedServers,
    isAvailable,
    maxSelected,
    load,
    createServer,
    updateServer,
    deleteServer,
    testServer,
    loadTools,
    toggleSelection,
    loadSessionBinding,
    resetDraftSelection,
    dispose,
  };
}
